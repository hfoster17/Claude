// =============================================================================
// MultiRegimeStrategy.cs — Institutional Multi-Futures HMM Regime Strategy
// NinjaTrader 8 — Full compilable strategy
//
// Architecture:
//   FeatureEngine → HmmFilter (internal) + ExternalRegimeClient (TCP)
//   → RegimeDecider → TradePolicy → RiskEngine → ExecManager → Telemetry
//
// Supports: NQ, ES, CL, NG, GC, SI, ZB
// =============================================================================

#region Using declarations
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.IO;
using System.Linq;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Windows.Media;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.Strategies;
#endregion

namespace NinjaTrader.NinjaScript.Strategies
{
    public class MultiRegimeStrategy : Strategy
    {
        // =====================================================================
        // INSTRUMENT PROFILE
        // =====================================================================
        private class InstrumentProfile
        {
            public string Symbol;
            public int K;
            public int FeatureWindow;
            public double ConfidenceThreshold;
            public int DwellBars;
            public int MaxFlips;
            public double StopAtrMult;
            public double TargetAtrMult;
            public int FlattenMinutes;
            public int MaxSize;
            public double TickSize;
            public double PointValue;
        }

        private static readonly Dictionary<string, InstrumentProfile> Profiles =
            new Dictionary<string, InstrumentProfile>
        {
            {"NQ", new InstrumentProfile{Symbol="NQ", K=3, FeatureWindow=20, ConfidenceThreshold=0.55,
                DwellBars=3, MaxFlips=6, StopAtrMult=2.0, TargetAtrMult=3.0, FlattenMinutes=5, MaxSize=2, TickSize=0.25, PointValue=20.0}},
            {"ES", new InstrumentProfile{Symbol="ES", K=3, FeatureWindow=20, ConfidenceThreshold=0.55,
                DwellBars=3, MaxFlips=6, StopAtrMult=2.0, TargetAtrMult=3.0, FlattenMinutes=5, MaxSize=4, TickSize=0.25, PointValue=50.0}},
            {"CL", new InstrumentProfile{Symbol="CL", K=3, FeatureWindow=20, ConfidenceThreshold=0.60,
                DwellBars=4, MaxFlips=5, StopAtrMult=1.5, TargetAtrMult=2.5, FlattenMinutes=10, MaxSize=2, TickSize=0.01, PointValue=1000.0}},
            {"NG", new InstrumentProfile{Symbol="NG", K=3, FeatureWindow=20, ConfidenceThreshold=0.60,
                DwellBars=4, MaxFlips=4, StopAtrMult=1.5, TargetAtrMult=2.5, FlattenMinutes=10, MaxSize=1, TickSize=0.001, PointValue=10000.0}},
            {"GC", new InstrumentProfile{Symbol="GC", K=3, FeatureWindow=20, ConfidenceThreshold=0.55,
                DwellBars=3, MaxFlips=5, StopAtrMult=2.0, TargetAtrMult=3.0, FlattenMinutes=10, MaxSize=2, TickSize=0.10, PointValue=100.0}},
            {"SI", new InstrumentProfile{Symbol="SI", K=3, FeatureWindow=20, ConfidenceThreshold=0.60,
                DwellBars=4, MaxFlips=4, StopAtrMult=1.5, TargetAtrMult=2.5, FlattenMinutes=10, MaxSize=1, TickSize=0.005, PointValue=5000.0}},
            {"ZB", new InstrumentProfile{Symbol="ZB", K=3, FeatureWindow=20, ConfidenceThreshold=0.55,
                DwellBars=3, MaxFlips=5, StopAtrMult=2.0, TargetAtrMult=3.0, FlattenMinutes=5, MaxSize=2, TickSize=0.03125, PointValue=1000.0}},
        };

        // =====================================================================
        // FEATURE ENGINE
        // =====================================================================
        private class FeatureEngine
        {
            private const int N_FEATURES = 6;
            private const double FLOOR = 1e-10;

            private readonly List<double> logReturns = new List<double>();
            private readonly List<double> retForZscore = new List<double>();
            private readonly List<double> volForZscore = new List<double>();
            private readonly List<double> volBuf = new List<double>();
            private double prevClose = double.NaN;
            private double cumPV, cumVol;
            private int barCount;

            public double[] Features { get; private set; } = new double[N_FEATURES];
            public bool Ready => barCount >= 100;

            public void ResetSession() { cumPV = 0; cumVol = 0; }

            public double[] Update(double open_, double high, double low, double close,
                                   double volume, double rsi14, double atr14, bool sessionReset)
            {
                if (sessionReset) ResetSession();
                barCount++;

                // Feature 0: Log Return z-scored
                double logRet = 0;
                if (!double.IsNaN(prevClose) && prevClose > 0)
                    logRet = Math.Log(close / prevClose);

                AddCapped(retForZscore, logRet, 100);
                double retMean = Mean(retForZscore);
                double retStd = Math.Max(Std(retForZscore), FLOOR);
                Features[0] = (logRet - retMean) / retStd;

                // Feature 1: Realized Vol z-scored
                AddCapped(logReturns, logRet, 20);
                double rv = logReturns.Count >= 2 ? Std(logReturns) : 0;
                AddCapped(volForZscore, rv, 100);
                double volMean = Mean(volForZscore);
                double volStd = Math.Max(Std(volForZscore), FLOOR);
                Features[1] = (rv - volMean) / volStd;

                // Feature 2: RSI deviation
                Features[2] = (rsi14 - 50.0) / 50.0;

                // Feature 3: VWAP distance
                double typical = (high + low + close) / 3.0;
                cumPV += typical * volume;
                cumVol += volume;
                double vwap = cumPV / Math.Max(cumVol, FLOOR);
                double safeAtr = Math.Max(atr14, FLOOR);
                Features[3] = Clip((close - vwap) / safeAtr, -3.0, 3.0);

                // Feature 4: Bar range ratio
                Features[4] = Clip((high - low) / safeAtr, 0.0, 5.0);

                // Feature 5: Volume z-score
                AddCapped(volBuf, volume, 20);
                if (volBuf.Count >= 2)
                {
                    double vm = Mean(volBuf);
                    double vs = Math.Max(Std(volBuf), FLOOR);
                    Features[5] = Clip((volume - vm) / vs, -3.0, 3.0);
                }
                else Features[5] = 0;

                // NaN safety
                for (int i = 0; i < N_FEATURES; i++)
                    if (double.IsNaN(Features[i]) || double.IsInfinity(Features[i]))
                        Features[i] = 0;

                prevClose = close;
                return Features;
            }

            private static void AddCapped(List<double> list, double val, int max)
            {
                list.Add(val);
                if (list.Count > max) list.RemoveAt(0);
            }

            private static double Mean(List<double> list)
            {
                if (list.Count == 0) return 0;
                double sum = 0;
                for (int i = 0; i < list.Count; i++) sum += list[i];
                return sum / list.Count;
            }

            private static double Std(List<double> list)
            {
                int n = list.Count;
                if (n < 2) return 0;
                double m = Mean(list);
                double sumSq = 0;
                for (int i = 0; i < n; i++) sumSq += (list[i] - m) * (list[i] - m);
                return Math.Sqrt(sumSq / (n - 1));
            }

            private static double Clip(double v, double lo, double hi)
            {
                if (v < lo) return lo;
                if (v > hi) return hi;
                return v;
            }
        }

        // =====================================================================
        // HMM MODEL (JSON-loaded)
        // =====================================================================
        private class HmmModelData
        {
            public int K;
            public int NFeatures;
            public double[] InitialProbs;
            public double[][] TransitionMatrix;
            public double[][] Means;
            public double[][] Variances;
            public string[] RegimeLabels;
            public int SchemaVersion;
        }

        // =====================================================================
        // HMM FILTER (Scaled Forward Algorithm)
        // =====================================================================
        private class HmmFilter
        {
            private readonly HmmModelData model;
            private double[] alpha;
            private const double VARIANCE_FLOOR = 1e-6;

            public double[] StateProbs => alpha;
            public int DominantState { get; private set; }
            public double Confidence { get; private set; }

            public HmmFilter(HmmModelData model)
            {
                this.model = model;
                alpha = new double[model.K];
                Array.Copy(model.InitialProbs, alpha, model.K);
            }

            public void Reset()
            {
                Array.Copy(model.InitialProbs, alpha, model.K);
            }

            public void Update(double[] obs)
            {
                int k = model.K;
                double[] alphaPred = new double[k];

                // Predict
                for (int j = 0; j < k; j++)
                {
                    double sum = 0;
                    for (int i = 0; i < k; i++)
                        sum += alpha[i] * model.TransitionMatrix[i][j];
                    alphaPred[j] = sum;
                }

                // Emission + update
                double[] logAlpha = new double[k];
                for (int j = 0; j < k; j++)
                {
                    double logEmit = LogGaussian(obs, model.Means[j], model.Variances[j]);
                    logAlpha[j] = Math.Log(Math.Max(alphaPred[j], 1e-300)) + logEmit;
                }

                // Log-sum-exp normalization
                double maxLog = logAlpha[0];
                for (int j = 1; j < k; j++)
                    if (logAlpha[j] > maxLog) maxLog = logAlpha[j];

                double sumExp = 0;
                for (int j = 0; j < k; j++)
                    sumExp += Math.Exp(logAlpha[j] - maxLog);

                double logSum = maxLog + Math.Log(sumExp);

                for (int j = 0; j < k; j++)
                    alpha[j] = Math.Exp(logAlpha[j] - logSum);

                // Normalize
                double total = 0;
                for (int j = 0; j < k; j++) total += alpha[j];
                if (total > 0 && !double.IsNaN(total))
                    for (int j = 0; j < k; j++) alpha[j] /= total;
                else
                    for (int j = 0; j < k; j++) alpha[j] = 1.0 / k;

                // Find dominant
                DominantState = 0;
                Confidence = alpha[0];
                for (int j = 1; j < k; j++)
                {
                    if (alpha[j] > Confidence)
                    {
                        DominantState = j;
                        Confidence = alpha[j];
                    }
                }
            }

            private double LogGaussian(double[] obs, double[] mean, double[] var)
            {
                int n = obs.Length;
                double logDet = 0, mahal = 0;
                for (int i = 0; i < n; i++)
                {
                    double v = Math.Max(var[i], VARIANCE_FLOOR);
                    logDet += Math.Log(v);
                    double d = obs[i] - mean[i];
                    mahal += d * d / v;
                }
                return -0.5 * (n * Math.Log(2 * Math.PI) + logDet + mahal);
            }
        }

        // =====================================================================
        // EXTERNAL REGIME CLIENT (TCP Background Thread)
        // =====================================================================
        private class RegimeResponse
        {
            public double[] StateProbs;
            public int State;
            public double Confidence;
            public int Version;
            public DateTime Timestamp;
            public bool IsValid;
        }

        private class ExternalRegimeClient
        {
            private readonly string host;
            private readonly int port;
            private readonly int timeoutMs;
            private Thread thread;
            private volatile bool running;
            private TcpClient client;
            private NetworkStream stream;
            private readonly ConcurrentQueue<string> requestQueue = new ConcurrentQueue<string>();
            private readonly ConcurrentQueue<RegimeResponse> responseQueue = new ConcurrentQueue<RegimeResponse>();
            private DateTime lastHeartbeatAck = DateTime.MinValue;
            private DateTime lastHeartbeatSent = DateTime.MinValue;
            private int reconnectAttempts;

            public bool IsConnected { get; private set; }
            public bool IsStale => (DateTime.UtcNow - lastHeartbeatAck).TotalSeconds > 60 && lastHeartbeatAck != DateTime.MinValue;
            public int StaleCount { get; private set; }

            public ExternalRegimeClient(string host, int port, int timeoutMs)
            {
                this.host = host;
                this.port = port;
                this.timeoutMs = timeoutMs;
            }

            public void Start()
            {
                running = true;
                thread = new Thread(RunLoop) { IsBackground = true, Name = "RegimeClient" };
                thread.Start();
            }

            public void Stop()
            {
                running = false;
                try { client?.Close(); } catch { }
                thread?.Join(5000);
            }

            public void EnqueueRequest(string symbol, DateTime timestamp, double[] features)
            {
                var sb = new StringBuilder();
                sb.Append("{\"type\":\"infer\",\"symbol\":\"").Append(symbol);
                sb.Append("\",\"timestamp\":\"").Append(timestamp.ToString("o"));
                sb.Append("\",\"features\":[");
                for (int i = 0; i < features.Length; i++)
                {
                    if (i > 0) sb.Append(',');
                    sb.Append(features[i].ToString("G10"));
                }
                sb.Append("]}");
                requestQueue.Enqueue(sb.ToString());
            }

            public RegimeResponse DequeueResponse()
            {
                if (responseQueue.TryDequeue(out var resp))
                    return resp;
                return null;
            }

            private void RunLoop()
            {
                while (running)
                {
                    try
                    {
                        if (!IsConnected) TryConnect();
                        if (!IsConnected) { Thread.Sleep(1000); continue; }

                        // Send heartbeat
                        if ((DateTime.UtcNow - lastHeartbeatSent).TotalSeconds >= 30)
                        {
                            SendMessage("{\"type\":\"heartbeat\"}");
                            lastHeartbeatSent = DateTime.UtcNow;
                        }

                        // Process requests
                        while (requestQueue.TryDequeue(out var req))
                        {
                            SendMessage(req);
                            var resp = ReceiveMessage();
                            if (resp != null)
                            {
                                var parsed = ParseResponse(resp);
                                if (parsed != null)
                                    responseQueue.Enqueue(parsed);
                            }
                        }

                        // Check for incoming data (heartbeat acks)
                        if (stream != null && stream.DataAvailable)
                        {
                            var msg = ReceiveMessage();
                            if (msg != null && msg.Contains("heartbeat_ack"))
                            {
                                lastHeartbeatAck = DateTime.UtcNow;
                                reconnectAttempts = 0;
                            }
                        }

                        Thread.Sleep(10);
                    }
                    catch (Exception)
                    {
                        IsConnected = false;
                        try { client?.Close(); } catch { }
                    }
                }
            }

            private void TryConnect()
            {
                if (reconnectAttempts >= 10) return;

                try
                {
                    client = new TcpClient();
                    client.SendTimeout = timeoutMs;
                    client.ReceiveTimeout = timeoutMs;
                    var result = client.BeginConnect(host, port, null, null);
                    bool connected = result.AsyncWaitHandle.WaitOne(timeoutMs);
                    if (connected && client.Connected)
                    {
                        client.EndConnect(result);
                        stream = client.GetStream();
                        IsConnected = true;
                        reconnectAttempts = 0;
                        lastHeartbeatAck = DateTime.UtcNow;
                    }
                    else
                    {
                        client.Close();
                        reconnectAttempts++;
                        int delay = Math.Min(1000 * (1 << reconnectAttempts), 30000);
                        Thread.Sleep(delay);
                    }
                }
                catch
                {
                    reconnectAttempts++;
                    int delay = Math.Min(1000 * (1 << reconnectAttempts), 30000);
                    Thread.Sleep(delay);
                }
            }

            private void SendMessage(string json)
            {
                if (stream == null || !IsConnected) return;
                byte[] payload = Encoding.UTF8.GetBytes(json);
                byte[] header = BitConverter.GetBytes(payload.Length);
                if (BitConverter.IsLittleEndian) Array.Reverse(header);
                stream.Write(header, 0, 4);
                stream.Write(payload, 0, payload.Length);
                stream.Flush();
            }

            private string ReceiveMessage()
            {
                if (stream == null || !IsConnected) return null;
                byte[] header = new byte[4];
                int read = 0;
                while (read < 4)
                {
                    int n = stream.Read(header, read, 4 - read);
                    if (n == 0) { IsConnected = false; return null; }
                    read += n;
                }
                if (BitConverter.IsLittleEndian) Array.Reverse(header);
                int len = BitConverter.ToInt32(header, 0);
                if (len <= 0 || len > 65536) return null;

                byte[] payload = new byte[len];
                read = 0;
                while (read < len)
                {
                    int n = stream.Read(payload, read, len - read);
                    if (n == 0) { IsConnected = false; return null; }
                    read += n;
                }
                return Encoding.UTF8.GetString(payload);
            }

            private RegimeResponse ParseResponse(string json)
            {
                try
                {
                    if (!json.Contains("\"type\":\"result\"")) return null;

                    var resp = new RegimeResponse { Timestamp = DateTime.UtcNow, IsValid = true };

                    // Simple JSON parsing (avoid external dependencies)
                    resp.State = ExtractInt(json, "state");
                    resp.Confidence = ExtractDouble(json, "confidence");
                    resp.Version = ExtractInt(json, "version");

                    // Parse state_probs array
                    int probStart = json.IndexOf("\"state_probs\":[") + 15;
                    int probEnd = json.IndexOf(']', probStart);
                    if (probStart > 14 && probEnd > probStart)
                    {
                        string[] parts = json.Substring(probStart, probEnd - probStart).Split(',');
                        resp.StateProbs = new double[parts.Length];
                        for (int i = 0; i < parts.Length; i++)
                            double.TryParse(parts[i].Trim(), out resp.StateProbs[i]);
                    }

                    return resp;
                }
                catch { return null; }
            }

            private static int ExtractInt(string json, string key)
            {
                string search = "\"" + key + "\":";
                int idx = json.IndexOf(search);
                if (idx < 0) return 0;
                idx += search.Length;
                while (idx < json.Length && json[idx] == ' ') idx++;
                int end = idx;
                while (end < json.Length && (char.IsDigit(json[end]) || json[end] == '-')) end++;
                int.TryParse(json.Substring(idx, end - idx), out int val);
                return val;
            }

            private static double ExtractDouble(string json, string key)
            {
                string search = "\"" + key + "\":";
                int idx = json.IndexOf(search);
                if (idx < 0) return 0;
                idx += search.Length;
                while (idx < json.Length && json[idx] == ' ') idx++;
                int end = idx;
                while (end < json.Length && (char.IsDigit(json[end]) || json[end] == '.' || json[end] == '-' || json[end] == 'e' || json[end] == 'E' || json[end] == '+')) end++;
                double.TryParse(json.Substring(idx, end - idx), System.Globalization.NumberStyles.Float,
                    System.Globalization.CultureInfo.InvariantCulture, out double val);
                return val;
            }
        }

        // =====================================================================
        // REGIME DECIDER (Hysteresis + Dwell + Flip Limiter)
        // =====================================================================
        private class RegimeDecider
        {
            private int currentRegime = -1;
            private int candidateRegime = -1;
            private int dwellCounter;
            private int flipCount;
            private readonly int dwellBars;
            private readonly int maxFlips;
            private readonly double confidenceThreshold;

            public int Regime => currentRegime;
            public int FlipCount => flipCount;

            public RegimeDecider(int dwellBars, int maxFlips, double confidenceThreshold)
            {
                this.dwellBars = dwellBars;
                this.maxFlips = maxFlips;
                this.confidenceThreshold = confidenceThreshold;
            }

            public void ResetSession()
            {
                flipCount = 0;
            }

            public int Update(int proposedState, double confidence)
            {
                // Below confidence threshold — hold current
                if (confidence < confidenceThreshold)
                    return currentRegime;

                // Flip limiter
                if (flipCount >= maxFlips)
                    return currentRegime;

                // Initialize
                if (currentRegime < 0)
                {
                    currentRegime = proposedState;
                    candidateRegime = proposedState;
                    dwellCounter = dwellBars;
                    return currentRegime;
                }

                // Same as current — reset candidate
                if (proposedState == currentRegime)
                {
                    candidateRegime = currentRegime;
                    dwellCounter = 0;
                    return currentRegime;
                }

                // Different — count dwell
                if (proposedState == candidateRegime)
                {
                    dwellCounter++;
                }
                else
                {
                    candidateRegime = proposedState;
                    dwellCounter = 1;
                }

                // Dwell met — switch
                if (dwellCounter >= dwellBars)
                {
                    currentRegime = candidateRegime;
                    flipCount++;
                    dwellCounter = 0;
                }

                return currentRegime;
            }
        }

        // =====================================================================
        // RISK ENGINE (State Machine)
        // =====================================================================
        private enum RiskState { Idle, Armed, InTrade, Locked, Halted, EmergencyStop }

        private class RiskEngine
        {
            public RiskState State { get; private set; } = RiskState.Idle;
            public double DailyPnL { get; private set; }
            public int TradeCount { get; private set; }
            public int ConsecutiveLosses { get; private set; }

            private readonly double dailyMaxLoss;
            private readonly double dailyProfitLock;
            private readonly int maxTrades;
            private readonly int consecutiveLockCount;

            public RiskEngine(double dailyMaxLoss, double dailyProfitLock,
                              int maxTrades, int consecutiveLockCount)
            {
                this.dailyMaxLoss = dailyMaxLoss;
                this.dailyProfitLock = dailyProfitLock;
                this.maxTrades = maxTrades;
                this.consecutiveLockCount = consecutiveLockCount;
            }

            public void ResetDaily()
            {
                if (State != RiskState.EmergencyStop)
                {
                    State = RiskState.Idle;
                    DailyPnL = 0;
                    TradeCount = 0;
                    ConsecutiveLosses = 0;
                }
            }

            public void SetEmergencyStop()
            {
                State = RiskState.EmergencyStop;
            }

            public bool CanEnter()
            {
                return State == RiskState.Idle || State == RiskState.Armed;
            }

            public void OnSignal()
            {
                if (State == RiskState.Idle)
                    State = RiskState.Armed;
            }

            public void OnEntryFill()
            {
                if (State == RiskState.Armed || State == RiskState.Idle)
                {
                    State = RiskState.InTrade;
                    TradeCount++;
                }
            }

            public void OnExitFill(double tradePnL)
            {
                DailyPnL += tradePnL;

                if (tradePnL < 0)
                    ConsecutiveLosses++;
                else
                    ConsecutiveLosses = 0;

                // Check limits
                if (DailyPnL <= -dailyMaxLoss)
                {
                    State = RiskState.Locked;
                    return;
                }

                if (dailyProfitLock > 0 && DailyPnL >= dailyProfitLock)
                {
                    State = RiskState.Locked;
                    return;
                }

                if (ConsecutiveLosses >= consecutiveLockCount)
                {
                    State = RiskState.Locked;
                    return;
                }

                if (TradeCount >= maxTrades)
                {
                    State = RiskState.Halted;
                    return;
                }

                State = RiskState.Idle;
            }
        }

        // =====================================================================
        // PROPERTIES
        // =====================================================================

        // Auto Profile
        [NinjaScriptProperty]
        [Display(Name = "Use Auto Profile", Order = 1, GroupName = "1. Auto Profile")]
        public bool UseAutoProfile { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Profile Symbol Override", Order = 2, GroupName = "1. Auto Profile")]
        public string ProfileSymbolOverride { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Model Config Folder", Order = 3, GroupName = "1. Auto Profile")]
        public string ModelConfigFolder { get; set; }

        // External Engine
        [NinjaScriptProperty]
        [Display(Name = "Enable External Engine", Order = 1, GroupName = "2. External Engine")]
        public bool EnableExternalEngine { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Host", Order = 2, GroupName = "2. External Engine")]
        public string Host { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Port", Order = 3, GroupName = "2. External Engine")]
        public int Port { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Timeout (ms)", Order = 4, GroupName = "2. External Engine")]
        public int TimeoutMs { get; set; }

        // Regime
        [NinjaScriptProperty]
        [Display(Name = "Confidence Threshold", Order = 1, GroupName = "3. Regime")]
        public double ConfidenceThreshold { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Dwell Bars", Order = 2, GroupName = "3. Regime")]
        public int DwellBars { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Max Flips", Order = 3, GroupName = "3. Regime")]
        public int MaxFlips { get; set; }

        // Risk
        [NinjaScriptProperty]
        [Display(Name = "Daily Max Loss", Order = 1, GroupName = "4. Risk")]
        public double DailyMaxLoss { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Daily Profit Lock", Order = 2, GroupName = "4. Risk")]
        public double DailyProfitLock { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Max Trades Per Day", Order = 3, GroupName = "4. Risk")]
        public int MaxTradesPerDay { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Consecutive Loss Lock Count", Order = 4, GroupName = "4. Risk")]
        public int ConsecutiveLossLockCount { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Flatten Minutes Before Close", Order = 5, GroupName = "4. Risk")]
        public int FlattenMinutesBeforeClose { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Enable Longs", Order = 6, GroupName = "4. Risk")]
        public bool EnableLongs { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Enable Shorts", Order = 7, GroupName = "4. Risk")]
        public bool EnableShorts { get; set; }

        // System
        [NinjaScriptProperty]
        [Display(Name = "Debug Enabled", Order = 1, GroupName = "5. System")]
        public bool DebugEnabled { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Emergency Kill Switch", Order = 2, GroupName = "5. System")]
        public bool EmergencyKillSwitch { get; set; }

        // =====================================================================
        // PRIVATE STATE
        // =====================================================================
        private FeatureEngine featureEngine;
        private HmmFilter hmmFilter;
        private ExternalRegimeClient externalClient;
        private RegimeDecider regimeDecider;
        private RiskEngine riskEngine;
        private InstrumentProfile activeProfile;
        private HmmModelData modelData;

        private RSI rsiIndicator;
        private ATR atrIndicator;

        private bool safeMode;
        private string safeModeReason = "";
        private bool sessionResetPending;
        private double entryPrice;
        private int entryDirection; // 1=long, -1=short, 0=flat
        private DateTime lastSessionResetDate = DateTime.MinValue;

        // =====================================================================
        // LIFECYCLE
        // =====================================================================
        protected override void OnStateChange()
        {
            if (State == NinjaTrader.NinjaScript.State.SetDefaults)
            {
                Description = "Multi-Regime HMM Strategy — Institutional Grade";
                Name = "MultiRegimeStrategy";
                Calculate = Calculate.OnBarClose;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 300;
                IsFillLimitOnTouch = false;
                MaximumBarsLookBack = MaximumBarsLookBack.TwoHundredFiftySix;
                OrderFillResolution = OrderFillResolution.Standard;
                IsInstantiatedOnEachOptimizationIteration = true;
                StartBehavior = StartBehavior.WaitUntilFlat;
                IsUnmanaged = false;

                // Defaults
                UseAutoProfile = true;
                ProfileSymbolOverride = "";
                ModelConfigFolder = @"C:\MultiRegime\models";
                EnableExternalEngine = true;
                Host = "127.0.0.1";
                Port = 5555;
                TimeoutMs = 2000;
                ConfidenceThreshold = 0.55;
                DwellBars = 3;
                MaxFlips = 6;
                DailyMaxLoss = 2000;
                DailyProfitLock = 5000;
                MaxTradesPerDay = 10;
                ConsecutiveLossLockCount = 3;
                FlattenMinutesBeforeClose = 5;
                EnableLongs = true;
                EnableShorts = true;
                DebugEnabled = false;
                EmergencyKillSwitch = false;
            }
            else if (State == NinjaTrader.NinjaScript.State.Configure)
            {
                rsiIndicator = RSI(14, 1);
                atrIndicator = ATR(14);
                AddChartIndicator(rsiIndicator);
                AddChartIndicator(atrIndicator);
            }
            else if (State == NinjaTrader.NinjaScript.State.DataLoaded)
            {
                InitializeComponents();
            }
            else if (State == NinjaTrader.NinjaScript.State.Terminated)
            {
                Cleanup();
            }
        }

        private void InitializeComponents()
        {
            safeMode = false;
            safeModeReason = "";

            // Detect instrument and load profile
            activeProfile = ResolveProfile();
            if (activeProfile == null)
            {
                safeMode = true;
                safeModeReason = "No profile found for instrument";
                return;
            }

            // Apply profile to properties if auto
            if (UseAutoProfile)
            {
                ConfidenceThreshold = activeProfile.ConfidenceThreshold;
                DwellBars = activeProfile.DwellBars;
                MaxFlips = activeProfile.MaxFlips;
                FlattenMinutesBeforeClose = activeProfile.FlattenMinutes;
            }

            // Feature engine
            featureEngine = new FeatureEngine();

            // Load HMM model
            modelData = LoadModel(activeProfile.Symbol);
            if (modelData != null)
            {
                hmmFilter = new HmmFilter(modelData);
            }
            else
            {
                safeMode = true;
                safeModeReason = "Model file not found — running in safe mode";
            }

            // Regime decider
            regimeDecider = new RegimeDecider(DwellBars, MaxFlips, ConfidenceThreshold);

            // Risk engine
            riskEngine = new RiskEngine(DailyMaxLoss, DailyProfitLock, MaxTradesPerDay, ConsecutiveLossLockCount);

            if (EmergencyKillSwitch)
                riskEngine.SetEmergencyStop();

            // External client
            if (EnableExternalEngine && !safeMode)
            {
                externalClient = new ExternalRegimeClient(Host, Port, TimeoutMs);
                externalClient.Start();
            }

            if (DebugEnabled)
                Print(string.Format("[MultiRegime] Initialized for {0}, K={1}, SafeMode={2}",
                    activeProfile.Symbol, activeProfile.K, safeMode));
        }

        private InstrumentProfile ResolveProfile()
        {
            string sym = "";

            if (!string.IsNullOrEmpty(ProfileSymbolOverride))
            {
                sym = ProfileSymbolOverride.ToUpper();
            }
            else
            {
                string instrName = Instrument.MasterInstrument.Name.ToUpper();
                foreach (var key in Profiles.Keys)
                {
                    if (instrName.Contains(key))
                    {
                        sym = key;
                        break;
                    }
                }
            }

            if (Profiles.ContainsKey(sym))
                return Profiles[sym];

            return null;
        }

        private HmmModelData LoadModel(string symbol)
        {
            string path = Path.Combine(ModelConfigFolder, symbol + "_model.json");
            if (!File.Exists(path))
            {
                if (DebugEnabled) Print("[MultiRegime] Model file not found: " + path);
                return null;
            }

            try
            {
                string json = File.ReadAllText(path);
                return ParseModelJson(json);
            }
            catch (Exception ex)
            {
                Print("[MultiRegime] Error loading model: " + ex.Message);
                return null;
            }
        }

        private HmmModelData ParseModelJson(string json)
        {
            // Simple manual JSON parser (avoids external library dependency)
            var m = new HmmModelData();

            m.SchemaVersion = (int)ExtractNumber(json, "schema_version");
            m.K = (int)ExtractNumber(json, "k");
            m.NFeatures = (int)ExtractNumber(json, "n_features");

            m.InitialProbs = ExtractArray(json, "initial_probs");
            m.TransitionMatrix = ExtractMatrix(json, "transition_matrix", m.K);
            m.Means = ExtractMatrix(json, "means", m.K);
            m.Variances = ExtractMatrix(json, "variances", m.K);

            // Parse regime labels
            m.RegimeLabels = ExtractStringArray(json, "regime_labels");

            // Validate
            if (m.K < 2 || m.InitialProbs == null || m.TransitionMatrix == null ||
                m.Means == null || m.Variances == null)
                return null;

            return m;
        }

        private static double ExtractNumber(string json, string key)
        {
            string search = "\"" + key + "\":";
            int idx = json.IndexOf(search);
            if (idx < 0) return 0;
            idx += search.Length;
            while (idx < json.Length && (json[idx] == ' ' || json[idx] == '\t')) idx++;
            int end = idx;
            while (end < json.Length && (char.IsDigit(json[end]) || json[end] == '.' || json[end] == '-')) end++;
            double.TryParse(json.Substring(idx, end - idx),
                System.Globalization.NumberStyles.Float,
                System.Globalization.CultureInfo.InvariantCulture, out double val);
            return val;
        }

        private static double[] ExtractArray(string json, string key)
        {
            string search = "\"" + key + "\":[";
            int idx = json.IndexOf(search);
            if (idx < 0) return null;
            idx += search.Length;
            int end = json.IndexOf(']', idx);
            if (end < 0) return null;
            string[] parts = json.Substring(idx, end - idx).Split(',');
            double[] result = new double[parts.Length];
            for (int i = 0; i < parts.Length; i++)
                double.TryParse(parts[i].Trim(),
                    System.Globalization.NumberStyles.Float,
                    System.Globalization.CultureInfo.InvariantCulture, out result[i]);
            return result;
        }

        private static double[][] ExtractMatrix(string json, string key, int rows)
        {
            string search = "\"" + key + "\":[";
            int start = json.IndexOf(search);
            if (start < 0) return null;
            start += search.Length;

            double[][] matrix = new double[rows][];
            for (int r = 0; r < rows; r++)
            {
                int rowStart = json.IndexOf('[', start) + 1;
                int rowEnd = json.IndexOf(']', rowStart);
                if (rowStart <= 0 || rowEnd < 0) return null;

                string[] parts = json.Substring(rowStart, rowEnd - rowStart).Split(',');
                matrix[r] = new double[parts.Length];
                for (int c = 0; c < parts.Length; c++)
                    double.TryParse(parts[c].Trim(),
                        System.Globalization.NumberStyles.Float,
                        System.Globalization.CultureInfo.InvariantCulture, out matrix[r][c]);
                start = rowEnd + 1;
            }
            return matrix;
        }

        private static string[] ExtractStringArray(string json, string key)
        {
            string search = "\"" + key + "\":[";
            int start = json.IndexOf(search);
            if (start < 0) return new string[0];
            start += search.Length;
            int end = json.IndexOf(']', start);
            if (end < 0) return new string[0];

            string content = json.Substring(start, end - start);
            var labels = new List<string>();
            int i = 0;
            while (i < content.Length)
            {
                int q1 = content.IndexOf('"', i);
                if (q1 < 0) break;
                int q2 = content.IndexOf('"', q1 + 1);
                if (q2 < 0) break;
                labels.Add(content.Substring(q1 + 1, q2 - q1 - 1));
                i = q2 + 1;
            }
            return labels.ToArray();
        }

        private void Cleanup()
        {
            externalClient?.Stop();
        }

        // =====================================================================
        // ON BAR UPDATE — MAIN LOGIC
        // =====================================================================
        protected override void OnBarUpdate()
        {
            if (CurrentBar < 100) return;

            // Emergency kill switch
            if (EmergencyKillSwitch)
            {
                if (Position.MarketPosition != MarketPosition.Flat)
                {
                    if (Position.MarketPosition == MarketPosition.Long)
                        ExitLong();
                    else if (Position.MarketPosition == MarketPosition.Short)
                        ExitShort();
                }
                return;
            }

            // Session reset detection
            bool sessionReset = false;
            if (Bars.IsFirstBarOfSession || Time[0].Date != lastSessionResetDate)
            {
                sessionReset = true;
                lastSessionResetDate = Time[0].Date;
                riskEngine?.ResetDaily();
                regimeDecider?.ResetSession();
            }

            // Flatten before session close
            if (ShouldFlatten())
            {
                FlattenPosition("Session close flatten");
                return;
            }

            // Safe mode — no trading, just telemetry
            if (safeMode || hmmFilter == null)
            {
                DrawTelemetry(-1, 0, "SAFE MODE: " + safeModeReason);
                return;
            }

            // 1. Compute features
            double[] features = featureEngine.Update(
                Open[0], High[0], Low[0], Close[0], Volume[0],
                rsiIndicator[0], atrIndicator[0], sessionReset);

            if (!featureEngine.Ready) return;

            // 2. Internal HMM update
            hmmFilter.Update(features);
            int internalState = hmmFilter.DominantState;
            double internalConf = hmmFilter.Confidence;

            // 3. External engine (non-blocking)
            int finalState = internalState;
            double finalConf = internalConf;

            if (externalClient != null && EnableExternalEngine)
            {
                externalClient.EnqueueRequest(activeProfile.Symbol, Time[0], features);
                var extResp = externalClient.DequeueResponse();
                if (extResp != null && extResp.IsValid)
                {
                    finalState = extResp.State;
                    finalConf = extResp.Confidence;
                }
            }

            // 4. Regime decider (hysteresis)
            int regime = regimeDecider.Update(finalState, finalConf);

            // 5. Trade policy
            int signal = GetTradeSignal(regime, finalConf);

            // 6. Risk engine gate
            if (!riskEngine.CanEnter() || signal == 0)
            {
                DrawTelemetry(regime, finalConf, "Risk: " + riskEngine.State);
                return;
            }

            riskEngine.OnSignal();

            // 7. Execution
            double atr = atrIndicator[0];
            double stopDist = atr * activeProfile.StopAtrMult;
            double targetDist = atr * activeProfile.TargetAtrMult;

            if (signal > 0 && EnableLongs && Position.MarketPosition != MarketPosition.Long)
            {
                if (Position.MarketPosition == MarketPosition.Short)
                    ExitShort();

                EnterLong(Math.Min(1, activeProfile.MaxSize), "RegimeLong");
                SetStopLoss("RegimeLong", CalculationMode.Ticks,
                    stopDist / Instrument.MasterInstrument.TickSize, false);
                SetProfitTarget("RegimeLong", CalculationMode.Ticks,
                    targetDist / Instrument.MasterInstrument.TickSize);
            }
            else if (signal < 0 && EnableShorts && Position.MarketPosition != MarketPosition.Short)
            {
                if (Position.MarketPosition == MarketPosition.Long)
                    ExitLong();

                EnterShort(Math.Min(1, activeProfile.MaxSize), "RegimeShort");
                SetStopLoss("RegimeShort", CalculationMode.Ticks,
                    stopDist / Instrument.MasterInstrument.TickSize, false);
                SetProfitTarget("RegimeShort", CalculationMode.Ticks,
                    targetDist / Instrument.MasterInstrument.TickSize);
            }

            DrawTelemetry(regime, finalConf, "");
        }

        private int GetTradeSignal(int regime, double confidence)
        {
            // Regime 0 = low_vol → no trade
            // Regime 1 = trending → trend follow (simple momentum)
            // Regime 2 = high_vol → mean revert
            if (regime < 0) return 0;

            string label = "";
            if (modelData != null && regime < modelData.RegimeLabels.Length)
                label = modelData.RegimeLabels[regime];

            if (label == "low_vol" || regime == 0)
                return 0; // No trade in low vol

            if (label == "trending" || regime == 1)
            {
                // Trend follow: buy if price above SMA-like proxy, sell if below
                double logRet = featureEngine.Features[0];
                if (logRet > 0.5) return 1;
                if (logRet < -0.5) return -1;
                return 0;
            }

            if (label == "high_vol" || regime == 2)
            {
                // Mean revert: fade extremes
                double rsiDev = featureEngine.Features[2];
                if (rsiDev < -0.4) return 1;  // Oversold → buy
                if (rsiDev > 0.4) return -1;   // Overbought → sell
                return 0;
            }

            return 0;
        }

        private bool ShouldFlatten()
        {
            if (FlattenMinutesBeforeClose <= 0) return false;
            if (Position.MarketPosition == MarketPosition.Flat) return false;

            var sessionEnd = Bars.SessionIterator.ActualSessionEnd;
            var minutesLeft = (sessionEnd - Time[0]).TotalMinutes;
            return minutesLeft <= FlattenMinutesBeforeClose;
        }

        private void FlattenPosition(string reason)
        {
            if (Position.MarketPosition == MarketPosition.Long)
                ExitLong("Flatten");
            else if (Position.MarketPosition == MarketPosition.Short)
                ExitShort("Flatten");

            if (DebugEnabled)
                Print("[MultiRegime] " + reason);
        }

        // =====================================================================
        // EXECUTION + ORDER TRACKING
        // =====================================================================
        protected override void OnExecutionUpdate(Execution execution, string executionId,
            double price, int quantity, MarketPosition marketPosition,
            string orderId, DateTime time)
        {
            if (riskEngine == null) return;

            if (execution.Order.OrderState == OrderState.Filled)
            {
                if (execution.Order.Name.StartsWith("Regime"))
                {
                    riskEngine.OnEntryFill();
                    entryPrice = price;
                    entryDirection = marketPosition == MarketPosition.Long ? 1 : -1;
                }
                else
                {
                    // Exit fill
                    double tradePnL = 0;
                    if (entryDirection == 1)
                        tradePnL = (price - entryPrice) * quantity * activeProfile.PointValue;
                    else if (entryDirection == -1)
                        tradePnL = (entryPrice - price) * quantity * activeProfile.PointValue;

                    riskEngine.OnExitFill(tradePnL);
                    entryDirection = 0;
                    entryPrice = 0;
                }
            }
        }

        // =====================================================================
        // TELEMETRY
        // =====================================================================
        private void DrawTelemetry(int regime, double confidence, string extra)
        {
            string regimeLabel = regime >= 0 && modelData != null && regime < modelData.RegimeLabels.Length
                ? modelData.RegimeLabels[regime] : "N/A";

            string riskLabel = riskEngine != null ? riskEngine.State.ToString() : "N/A";
            double pnl = riskEngine != null ? riskEngine.DailyPnL : 0;
            int trades = riskEngine != null ? riskEngine.TradeCount : 0;
            bool extConn = externalClient != null && externalClient.IsConnected;

            string text = string.Format("R:{0} C:{1:F2} | Risk:{2} PnL:{3:F0} T:{4} | Ext:{5}",
                regimeLabel, confidence, riskLabel, pnl, trades, extConn ? "ON" : "OFF");

            if (!string.IsNullOrEmpty(extra))
                text += " | " + extra;

            Draw.TextFixed(this, "RegimeLabel", text, TextPosition.TopRight,
                regime == 2 ? Brushes.Red : regime == 1 ? Brushes.DodgerBlue : Brushes.Gray,
                new Gui.Tools.SimpleFont("Consolas", 11), Brushes.Transparent, Brushes.Transparent, 0);
        }
    }
}
