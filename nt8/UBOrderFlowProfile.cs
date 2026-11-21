// =============================================================================
// UBOrderFlowProfile.cs — Ultra T-Bond (UB) Order-Flow Volume-Profile Strategy
// NinjaTrader 8
//
// Twin of engine/ub_orderflow_backtest.py — same rules, same defaults. Validate
// and tune there on your exported data, then copy parameters here.
//
// Logic (levels always come from the PRIOR RTH session -> no lookahead):
//   * Builds an RTH (07:20-14:00 CT) volume profile from Tick Replay trades,
//     classifying each trade buy/sell by bid/ask (tick rule fallback).
//   * POC / VAH / VAL with the standard 70% value-area expansion.
//   * REJECTION: bar probes beyond VAH/VAL, closes back inside, confirmed by a
//     delta flip OR absorption (big delta with the probe, close against it).
//     Target = prior POC. Stop = probe extreme + buffer.
//   * ACCEPTANCE: N consecutive closes outside value (fresh break), cumulative
//     delta ratio confirms, not over-extended. Stop back inside value, target RR.
//   * Risk: trade window, flatten time, max trades/day, daily $ loss limit,
//     consecutive-loss lockout, kill switch. Each setup once per session.
//
// SETUP: front-month UB contract, 5-minute chart, the instrument's default
// (ETH) trading hours, and ENABLE TICK REPLAY in the Data Series window.
// Without Tick Replay, historical delta is approximated from bars.
// =============================================================================

#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Windows.Media;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.Gui;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

namespace NinjaTrader.NinjaScript.Strategies
{
    public class UBOrderFlowProfile : Strategy
    {
        // ---------------------------------------------------------------------
        // Internal state
        // ---------------------------------------------------------------------
        private struct TickRec
        {
            public DateTime Time;
            public double Price;
            public double Volume;
            public int Side;
        }

        private readonly List<TickRec> tickBuffer = new List<TickRec>();
        private double lastTradePrice;
        private int lastTickDir = 1;

        private SortedDictionary<int, double> sessionProfile = new SortedDictionary<int, double>();
        private bool hasPrior;
        private double priorPoc, priorVah, priorVal;

        private DateTime curSessionDate = DateTime.MinValue;
        private bool inRthPrev;
        private int sessionStartBar;

        private readonly List<double> sessCloses = new List<double>();
        private readonly List<double> sessDeltas = new List<double>();
        private readonly List<double> sessVols = new List<double>();

        private bool usedRejShort, usedRejLong, usedAccLong, usedAccShort;

        private double dayPnl;
        private int dayTrades;
        private int consecLosses;
        private int lastTradeCount;

        private double pendingStop, pendingTarget;
        private string lastSetup = "";
        private TimeZoneInfo ctZone;
        private bool warnedNoTicks;

        private const string SigRejShort = "REJ_SHORT";
        private const string SigRejLong = "REJ_LONG";
        private const string SigAccLong = "ACC_LONG";
        private const string SigAccShort = "ACC_SHORT";

        // ---------------------------------------------------------------------
        // Lifecycle
        // ---------------------------------------------------------------------
        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "UBOrderFlowProfile";
                Description = "UB order-flow volume-profile strategy: value-area rejection and acceptance confirmed by delta.";
                Calculate = Calculate.OnBarClose;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 300;
                IsFillLimitOnTouch = false;
                MaximumBarsLookBack = MaximumBarsLookBack.TwoHundredFiftySix;
                OrderFillResolution = OrderFillResolution.Standard;
                Slippage = 1;
                StartBehavior = StartBehavior.WaitUntilFlat;
                TimeInForce = TimeInForce.Day;
                TraceOrders = false;
                RealtimeErrorHandling = RealtimeErrorHandling.StopCancelClose;
                StopTargetHandling = StopTargetHandling.PerEntryExecution;
                BarsRequiredToTrade = 1;
                IsInstantiatedOnEachOptimizationIteration = true;

                RthStart = "07:20";
                RthEnd = "14:00";
                TradeStart = "07:35";
                TradeEnd = "13:30";
                FlattenTime = "13:55";
                ValueAreaPct = 0.70;

                EnableRejection = true;
                ProbeTicks = 1;
                CloseInsideTicks = 1;
                FlipDeltaRatio = 0.05;
                AbsorbDeltaRatio = 0.15;
                StopBufferTicks = 2;
                MinStopTicks = 4;
                MaxStopTicks = 14;
                MinRR = 1.0;

                EnableAcceptance = true;
                AcceptBars = 3;
                AcceptDeltaRatio = 0.08;
                AcceptMaxExtTicks = 10;
                AcceptStopTicks = 8;
                AcceptRR = 1.5;

                Contracts = 1;
                MaxTradesPerDay = 3;
                MaxDailyLoss = 750;
                MaxConsecLosses = 2;
                KillSwitch = false;
                DrawLevels = true;
            }
            else if (State == State.DataLoaded)
            {
                try { ctZone = TimeZoneInfo.FindSystemTimeZoneById("Central Standard Time"); }
                catch { ctZone = Core.Globals.GeneralOptions.TimeZoneInfo; }
            }
            else if (State == State.Historical)
            {
                if (!IsTickReplays[0])
                    Print(Name + ": Tick Replay is OFF. Historical delta/profile will be APPROXIMATED from bars. Enable Tick Replay for real order flow.");
            }
        }

        // ---------------------------------------------------------------------
        // Tick ingestion: classify aggressor, buffer until the bar closes
        // ---------------------------------------------------------------------
        protected override void OnMarketData(MarketDataEventArgs e)
        {
            if (e.MarketDataType != MarketDataType.Last || e.Volume <= 0)
                return;

            int side;
            if (e.Ask > 0 && e.Price >= e.Ask) side = 1;
            else if (e.Bid > 0 && e.Price <= e.Bid) side = -1;
            else
            {
                if (lastTradePrice > 0 && e.Price > lastTradePrice) lastTickDir = 1;
                else if (lastTradePrice > 0 && e.Price < lastTradePrice) lastTickDir = -1;
                side = lastTickDir;
            }
            lastTradePrice = e.Price;

            tickBuffer.Add(new TickRec { Time = e.Time, Price = e.Price, Volume = e.Volume, Side = side });
        }

        // ---------------------------------------------------------------------
        // Bar close
        // ---------------------------------------------------------------------
        protected override void OnBarUpdate()
        {
            if (BarsInProgress != 0)
                return;
            if (CurrentBar < 1) { tickBuffer.Clear(); return; }

            // ---- consume ticks belonging to this bar (time <= bar close time)
            double buy = 0, sell = 0;
            var levels = new Dictionary<int, double>();
            int consumed = 0;
            for (; consumed < tickBuffer.Count; consumed++)
            {
                TickRec t = tickBuffer[consumed];
                if (t.Time > Time[0]) break;
                if (t.Side > 0) buy += t.Volume; else sell += t.Volume;
                int idx = PriceToIdx(t.Price);
                double v;
                levels.TryGetValue(idx, out v);
                levels[idx] = v + t.Volume;
            }
            if (consumed > 0) tickBuffer.RemoveRange(0, consumed);

            if (consumed == 0)
            {
                // No tick data: approximate (matches Python 'approx_clv' mode)
                if (!warnedNoTicks && State == State.Realtime)
                {
                    Print(Name + ": no ticks seen for a realtime bar — check data feed.");
                    warnedNoTicks = true;
                }
                double vol = Volume[0];
                double rng = High[0] - Low[0];
                double clv = rng > 0 ? (2 * (Close[0] - Low[0]) - rng) / rng : 0;
                buy = (vol + clv * vol) / 2;
                sell = (vol - clv * vol) / 2;
                int lo = PriceToIdx(Low[0]), hi = PriceToIdx(High[0]);
                int n = hi - lo + 1;
                for (int i = lo; i <= hi; i++) levels[i] = vol / n;
            }

            DateTime ct = ToCentral(Time[0]);
            TimeSpan tod = ct.TimeOfDay;
            bool inRth = tod > ParseTime(RthStart) && tod <= ParseTime(RthEnd);

            // ---- session roll
            if (inRth && (!inRthPrev || ct.Date != curSessionDate))
                RollSession(ct.Date);
            inRthPrev = inRth;

            // ---- flatten
            if (Position.MarketPosition != MarketPosition.Flat && (tod >= ParseTime(FlattenTime) || !inRth))
            {
                if (Position.MarketPosition == MarketPosition.Long) ExitLong("Flatten", "");
                else ExitShort("Flatten", "");
            }

            if (!inRth)
                return;

            foreach (var kv in levels)
            {
                double v;
                sessionProfile.TryGetValue(kv.Key, out v);
                sessionProfile[kv.Key] = v + kv.Value;
            }
            sessCloses.Add(Close[0]);
            sessDeltas.Add(buy - sell);
            sessVols.Add(buy + sell);

            if (DrawLevels && hasPrior) DrawPriorLevels();

            if (KillSwitch)
                return;
            if (Position.MarketPosition != MarketPosition.Flat || !hasPrior)
                return;
            if (tod < ParseTime(TradeStart) || tod > ParseTime(TradeEnd))
                return;
            if (dayTrades >= MaxTradesPerDay || dayPnl <= -MaxDailyLoss || consecLosses >= MaxConsecLosses)
                return;

            string sig = EvaluateSignals(High[0], Low[0], Close[0], buy, sell);
            if (sig == null)
                return;

            lastSetup = sig;
            SetStopLoss(sig, CalculationMode.Price, pendingStop, false);
            SetProfitTarget(sig, CalculationMode.Price, pendingTarget);
            if (sig == SigRejLong || sig == SigAccLong) EnterLong(Contracts, sig);
            else EnterShort(Contracts, sig);
            dayTrades++;

            Print(string.Format("{0} {1} signal close={2} stop={3} target={4} | prior POC={5} VAH={6} VAL={7}",
                ct, sig, Close[0], pendingStop, pendingTarget, priorPoc, priorVah, priorVal));
        }

        // ---------------------------------------------------------------------
        // Signal logic — mirror of evaluate_signal() in Python
        // ---------------------------------------------------------------------
        private string EvaluateSignals(double h, double l, double c, double buy, double sell)
        {
            double tick = TickSize;
            double vol = buy + sell;
            if (vol <= 0) return null;
            double dr = (buy - sell) / vol;
            double rng = h - l;
            double clv = rng > 0 ? (c - l) / rng : 0.5;

            if (EnableRejection)
            {
                if (!usedRejShort && h >= priorVah + ProbeTicks * tick
                    && c <= priorVah - CloseInsideTicks * tick && c > priorPoc)
                {
                    bool flip = dr <= -FlipDeltaRatio;
                    bool absorb = dr >= AbsorbDeltaRatio && clv <= 0.4;
                    if (flip || absorb)
                    {
                        double stop = h + StopBufferTicks * tick;
                        double risk = (stop - c) / tick;
                        if (risk < MinStopTicks) { stop = c + MinStopTicks * tick; risk = MinStopTicks; }
                        double reward = (c - priorPoc) / tick;
                        if (risk <= MaxStopTicks && reward >= MinRR * risk)
                        {
                            usedRejShort = true;
                            pendingStop = stop; pendingTarget = priorPoc;
                            return SigRejShort;
                        }
                    }
                }
                if (!usedRejLong && l <= priorVal - ProbeTicks * tick
                    && c >= priorVal + CloseInsideTicks * tick && c < priorPoc)
                {
                    bool flip = dr >= FlipDeltaRatio;
                    bool absorb = dr <= -AbsorbDeltaRatio && clv >= 0.6;
                    if (flip || absorb)
                    {
                        double stop = l - StopBufferTicks * tick;
                        double risk = (c - stop) / tick;
                        if (risk < MinStopTicks) { stop = c - MinStopTicks * tick; risk = MinStopTicks; }
                        double reward = (priorPoc - c) / tick;
                        if (risk <= MaxStopTicks && reward >= MinRR * risk)
                        {
                            usedRejLong = true;
                            pendingStop = stop; pendingTarget = priorPoc;
                            return SigRejLong;
                        }
                    }
                }
            }

            int n = AcceptBars;
            if (EnableAcceptance && sessCloses.Count > n)
            {
                int cnt = sessCloses.Count;
                double prior = sessCloses[cnt - n - 1];
                bool allAbove = true, allBelow = true;
                double sd = 0, sv = 0;
                for (int i = cnt - n; i < cnt; i++)
                {
                    if (sessCloses[i] <= priorVah) allAbove = false;
                    if (sessCloses[i] >= priorVal) allBelow = false;
                    sd += sessDeltas[i];
                    sv += sessVols[i];
                }
                double cdr = sv > 0 ? sd / sv : 0;

                if (!usedAccLong && allAbove && prior <= priorVah && cdr >= AcceptDeltaRatio
                    && (c - priorVah) / tick <= AcceptMaxExtTicks)
                {
                    double stop = priorVah - AcceptStopTicks * tick;
                    usedAccLong = true;
                    pendingStop = stop;
                    pendingTarget = RoundToTick(c + AcceptRR * (c - stop));
                    return SigAccLong;
                }
                if (!usedAccShort && allBelow && prior >= priorVal && cdr <= -AcceptDeltaRatio
                    && (priorVal - c) / tick <= AcceptMaxExtTicks)
                {
                    double stop = priorVal + AcceptStopTicks * tick;
                    usedAccShort = true;
                    pendingStop = stop;
                    pendingTarget = RoundToTick(c - AcceptRR * (stop - c));
                    return SigAccShort;
                }
            }
            return null;
        }

        // ---------------------------------------------------------------------
        // Session / profile
        // ---------------------------------------------------------------------
        private void RollSession(DateTime newDate)
        {
            if (sessionProfile.Count > 0)
            {
                int poc, vah, val;
                if (ComputeValueArea(sessionProfile, ValueAreaPct, out poc, out vah, out val))
                {
                    priorPoc = IdxToPrice(poc);
                    priorVah = IdxToPrice(vah);
                    priorVal = IdxToPrice(val);
                    hasPrior = true;
                }
            }
            sessionProfile = new SortedDictionary<int, double>();
            curSessionDate = newDate;
            sessionStartBar = CurrentBar;
            sessCloses.Clear(); sessDeltas.Clear(); sessVols.Clear();
            usedRejShort = usedRejLong = usedAccLong = usedAccShort = false;
            dayPnl = 0; dayTrades = 0; consecLosses = 0;
        }

        // Identical to value_area() in Python.
        private static bool ComputeValueArea(SortedDictionary<int, double> prof, double pct,
                                             out int poc, out int vah, out int val)
        {
            poc = vah = val = 0;
            if (prof.Count == 0) return false;
            int lo = prof.Keys.First(), hi = prof.Keys.Last();
            int n = hi - lo + 1;
            double[] vols = new double[n];
            double total = 0;
            foreach (var kv in prof) { vols[kv.Key - lo] = kv.Value; total += kv.Value; }
            if (total <= 0) return false;

            int pocOff = 0;
            for (int k = 1; k < n; k++)
                if (vols[k] > vols[pocOff]) pocOff = k;       // strict > keeps lower price on ties

            int up = pocOff, dn = pocOff;
            double acc = vols[pocOff], target = total * pct;
            while (acc < target && (up < n - 1 || dn > 0))
            {
                double a = -1, b = -1;
                if (up < n - 1) { a = 0; for (int k = up + 1; k < Math.Min(up + 3, n); k++) a += vols[k]; }
                if (dn > 0) { b = 0; for (int k = Math.Max(dn - 2, 0); k < dn; k++) b += vols[k]; }
                if (a >= b)
                {
                    int step = Math.Min(2, n - 1 - up);
                    for (int k = up + 1; k <= up + step; k++) acc += vols[k];
                    up += step;
                }
                else
                {
                    int step = Math.Min(2, dn);
                    for (int k = dn - step; k < dn; k++) acc += vols[k];
                    dn -= step;
                }
            }
            poc = lo + pocOff; vah = lo + up; val = lo + dn;
            return true;
        }

        // ---------------------------------------------------------------------
        // Executions / risk bookkeeping
        // ---------------------------------------------------------------------
        protected override void OnExecutionUpdate(Execution execution, string executionId, double price,
            int quantity, MarketPosition marketPosition, string orderId, DateTime time)
        {
            if (execution.Order == null || execution.Order.OrderState != OrderState.Filled)
                return;

            // Entry filled through the stop (gap) -> get out immediately.
            string n = execution.Order.Name;
            if (n == SigRejLong || n == SigAccLong)
            {
                if (price <= pendingStop) ExitLong("GapExit", n);
            }
            else if (n == SigRejShort || n == SigAccShort)
            {
                if (price >= pendingStop) ExitShort("GapExit", n);
            }
        }

        protected override void OnPositionUpdate(Position position, double averagePrice, int quantity,
            MarketPosition marketPosition)
        {
            if (marketPosition != MarketPosition.Flat)
                return;
            int count = SystemPerformance.AllTrades.Count;
            for (int i = lastTradeCount; i < count; i++)
            {
                double p = SystemPerformance.AllTrades[i].ProfitCurrency;
                dayPnl += p;
                consecLosses = p < 0 ? consecLosses + 1 : 0;
            }
            lastTradeCount = count;
        }

        // ---------------------------------------------------------------------
        // Helpers
        // ---------------------------------------------------------------------
        private int PriceToIdx(double p) { return (int)Math.Round(p / TickSize); }
        private double IdxToPrice(int i) { return i * TickSize; }
        private double RoundToTick(double p) { return Instrument.MasterInstrument.RoundToTickSize(p); }

        private DateTime ToCentral(DateTime local)
        {
            if (ctZone == null) return local;
            return TimeZoneInfo.ConvertTime(local, Core.Globals.GeneralOptions.TimeZoneInfo, ctZone);
        }

        private static TimeSpan ParseTime(string hhmm)
        {
            TimeSpan ts;
            return TimeSpan.TryParse(hhmm, out ts) ? ts : TimeSpan.Zero;
        }

        private void DrawPriorLevels()
        {
            int ago = Math.Max(0, CurrentBar - sessionStartBar);
            string d = curSessionDate.ToString("yyyyMMdd");
            Draw.Line(this, "VAH" + d, false, ago, priorVah, 0, priorVah, Brushes.IndianRed, DashStyleHelper.Dash, 2);
            Draw.Line(this, "VAL" + d, false, ago, priorVal, 0, priorVal, Brushes.MediumSeaGreen, DashStyleHelper.Dash, 2);
            Draw.Line(this, "POC" + d, false, ago, priorPoc, 0, priorPoc, Brushes.Gold, DashStyleHelper.Solid, 2);
            Draw.TextFixed(this, "UBOFStatus",
                string.Format("UB OF Profile | pVAH {0}  pPOC {1}  pVAL {2} | trades {3}/{4}  dayPnL ${5:F0}{6}",
                    FormatBond(priorVah), FormatBond(priorPoc), FormatBond(priorVal),
                    dayTrades, MaxTradesPerDay, dayPnl, KillSwitch ? "  [KILL SWITCH]" : ""),
                TextPosition.TopLeft);
        }

        private string FormatBond(double p)
        {
            return Instrument.MasterInstrument.FormatPrice(p);
        }

        // ---------------------------------------------------------------------
        // Properties
        // ---------------------------------------------------------------------
        [NinjaScriptProperty]
        [Display(Name = "RTH start (CT, HH:mm)", Order = 1, GroupName = "1. Session")]
        public string RthStart { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "RTH end (CT)", Order = 2, GroupName = "1. Session")]
        public string RthEnd { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Trade start (CT)", Order = 3, GroupName = "1. Session")]
        public string TradeStart { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Trade end (CT)", Order = 4, GroupName = "1. Session")]
        public string TradeEnd { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Flatten time (CT)", Order = 5, GroupName = "1. Session")]
        public string FlattenTime { get; set; }

        [NinjaScriptProperty]
        [Range(0.5, 0.95)]
        [Display(Name = "Value area %", Order = 6, GroupName = "1. Session")]
        public double ValueAreaPct { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Enable rejection", Order = 1, GroupName = "2. Rejection")]
        public bool EnableRejection { get; set; }

        [NinjaScriptProperty]
        [Range(0, 20)]
        [Display(Name = "Probe ticks beyond VA", Order = 2, GroupName = "2. Rejection")]
        public int ProbeTicks { get; set; }

        [NinjaScriptProperty]
        [Range(0, 20)]
        [Display(Name = "Close inside ticks", Order = 3, GroupName = "2. Rejection")]
        public int CloseInsideTicks { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 1.0)]
        [Display(Name = "Delta flip ratio", Order = 4, GroupName = "2. Rejection")]
        public double FlipDeltaRatio { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 1.0)]
        [Display(Name = "Absorption delta ratio", Order = 5, GroupName = "2. Rejection")]
        public double AbsorbDeltaRatio { get; set; }

        [NinjaScriptProperty]
        [Range(0, 20)]
        [Display(Name = "Stop buffer ticks", Order = 6, GroupName = "2. Rejection")]
        public int StopBufferTicks { get; set; }

        [NinjaScriptProperty]
        [Range(1, 50)]
        [Display(Name = "Min stop ticks", Order = 7, GroupName = "2. Rejection")]
        public int MinStopTicks { get; set; }

        [NinjaScriptProperty]
        [Range(1, 100)]
        [Display(Name = "Max stop ticks", Order = 8, GroupName = "2. Rejection")]
        public int MaxStopTicks { get; set; }

        [NinjaScriptProperty]
        [Range(0.1, 10)]
        [Display(Name = "Min reward:risk to POC", Order = 9, GroupName = "2. Rejection")]
        public double MinRR { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Enable acceptance", Order = 1, GroupName = "3. Acceptance")]
        public bool EnableAcceptance { get; set; }

        [NinjaScriptProperty]
        [Range(1, 20)]
        [Display(Name = "Accept bars outside VA", Order = 2, GroupName = "3. Acceptance")]
        public int AcceptBars { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 1.0)]
        [Display(Name = "Accept cum. delta ratio", Order = 3, GroupName = "3. Acceptance")]
        public double AcceptDeltaRatio { get; set; }

        [NinjaScriptProperty]
        [Range(0, 100)]
        [Display(Name = "Max extension ticks", Order = 4, GroupName = "3. Acceptance")]
        public int AcceptMaxExtTicks { get; set; }

        [NinjaScriptProperty]
        [Range(1, 100)]
        [Display(Name = "Stop ticks inside VA", Order = 5, GroupName = "3. Acceptance")]
        public int AcceptStopTicks { get; set; }

        [NinjaScriptProperty]
        [Range(0.1, 10)]
        [Display(Name = "Target R multiple", Order = 6, GroupName = "3. Acceptance")]
        public double AcceptRR { get; set; }

        [NinjaScriptProperty]
        [Range(1, 20)]
        [Display(Name = "Contracts", Order = 1, GroupName = "4. Risk")]
        public int Contracts { get; set; }

        [NinjaScriptProperty]
        [Range(1, 50)]
        [Display(Name = "Max trades per day", Order = 2, GroupName = "4. Risk")]
        public int MaxTradesPerDay { get; set; }

        [NinjaScriptProperty]
        [Range(0, 100000)]
        [Display(Name = "Max daily loss ($)", Order = 3, GroupName = "4. Risk")]
        public double MaxDailyLoss { get; set; }

        [NinjaScriptProperty]
        [Range(1, 20)]
        [Display(Name = "Max consecutive losses", Order = 4, GroupName = "4. Risk")]
        public int MaxConsecLosses { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "KILL SWITCH (no new entries)", Order = 5, GroupName = "4. Risk")]
        public bool KillSwitch { get; set; }

        [Display(Name = "Draw prior VA levels", Order = 1, GroupName = "5. Display")]
        public bool DrawLevels { get; set; }
    }
}
