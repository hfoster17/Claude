<#
.SYNOPSIS
    Reflects a compiled NinjaTrader 8 strategy and maps how its entry signals
    and scanners are wired: event handler -> internal methods -> order calls.

.DESCRIPTION
    Read-only. Loads the assembly that contains the target type, then writes:
      1. User-facing parameters ([NinjaScriptProperty]/[Display] attributes)
      2. Call trees rooted at every On* event handler (OnBarUpdate,
         OnMarketDepth, OnMarketData, OnStateChange, ...), annotated with
         order-entry calls (>> ORDER), NinjaTrader data/indicator API used,
         float constants (hard-coded thresholds) and string literals
         (signal names / Print text)
      3. Full member dump (fields, properties, methods + IL size)

    Run in *Windows PowerShell 5.1* (powershell.exe), not PowerShell 7,
    because NT8 targets .NET Framework 4.8. Close NinjaTrader first if the
    DLL is locked.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\Inspect-NinjaScript.ps1 -TypePattern L2A
#>
param(
    [string]$TypePattern = 'L2A',
    [string]$CustomDir   = "$env:USERPROFILE\Documents\NinjaTrader 8\bin\Custom",
    [string]$InstallDir  = "${env:ProgramFiles}\NinjaTrader 8",
    [string]$AssemblyPath,                       # skip the search and load this DLL
    [int]$MaxDepth       = 8,
    [string]$OutFile     = "$env:USERPROFILE\Desktop\$TypePattern`_inspect.txt"
)

$ErrorActionPreference = 'Stop'
$lines = [System.Collections.Generic.List[string]]::new()
function W([string]$s = '') { $lines.Add($s) }

# --- Resolve NT8 dependencies (NinjaTrader.Core, Gui, SharpDX, ...) on demand ---
$script:searchDirs = @((Join-Path $InstallDir 'bin'), $CustomDir) | Where-Object { $_ -and (Test-Path $_) }
[AppDomain]::CurrentDomain.add_AssemblyResolve([ResolveEventHandler]{
    param($s, $e)
    $file = (New-Object Reflection.AssemblyName $e.Name).Name + '.dll'
    foreach ($d in $script:searchDirs) {
        $p = Join-Path $d $file
        if (Test-Path $p) { return [Reflection.Assembly]::LoadFrom($p) }
    }
    return $null
})

function Get-LoadableTypes([Reflection.Assembly]$a) {
    # Missing dependencies are normal (e.g. SharpDX); keep the types that did load.
    # PowerShell wraps the exception, so unwrap to find ReflectionTypeLoadException.
    try { $a.GetTypes() }
    catch {
        $ex = $_.Exception
        while ($ex -and $ex -isnot [Reflection.ReflectionTypeLoadException]) { $ex = $ex.InnerException }
        if ($ex) { $ex.Types | Where-Object { $_ } }
    }
}

# --- Locate the assembly holding the target type ---
$candidates = if ($AssemblyPath) { @(Get-Item $AssemblyPath) }
              else { Get-ChildItem $CustomDir -Filter *.dll | Sort-Object { $_.Name -ne 'NinjaTrader.Custom.dll' } }
$asm = $null; $targets = @()
foreach ($f in $candidates) {
    try { $a = [Reflection.Assembly]::LoadFrom($f.FullName) } catch { continue }
    $hit = @(Get-LoadableTypes $a | Where-Object { $_.Name -match $TypePattern -and -not $_.IsNested })
    if ($hit) { $asm = $a; $targets = $hit; break }
}
if (-not $asm) { throw "No type matching '$TypePattern' found in $CustomDir. Pass -AssemblyPath explicitly." }

# A vendor DLL is usually all strategy code: include every type. In the shared
# NinjaTrader.Custom.dll, stick to the matching types and their nested types.
$isVendorDll = [IO.Path]::GetFileName($asm.Location) -ne 'NinjaTrader.Custom.dll'
$scopeTypes = if ($isVendorDll) { @(Get-LoadableTypes $asm) }
              else { @(Get-LoadableTypes $asm | Where-Object { $t = $_; $targets | Where-Object { $t -eq $_ -or $t.FullName.StartsWith($_.FullName + '+') } }) }

# --- IL walker ---
$op1 = @{}; $op2 = @{}
foreach ($fi in [Reflection.Emit.OpCodes].GetFields('Public,Static')) {
    $op = $fi.GetValue($null); $key = [int]$op.Value -band 0xFF
    if ($op.Size -eq 1) { $op1[$key] = $op } else { $op2[$key] = $op }
}
$script:protectedIL = 0

function Get-ILRefs([Reflection.MethodBase]$m) {
    $body = $null; try { $body = $m.GetMethodBody() } catch {}
    if (-not $body) { return }
    $il = $body.GetILAsByteArray(); $mod = $m.Module
    $tArgs = $null; $mArgs = $null
    try { if ($m.DeclaringType -and $m.DeclaringType.IsGenericType) { $tArgs = $m.DeclaringType.GetGenericArguments() } } catch {}
    try { if ($m.IsGenericMethod) { $mArgs = $m.GetGenericArguments() } } catch {}
    $i = 0
    while ($i -lt $il.Length) {
        $b = $il[$i]; $i++
        if ($b -eq 0xFE) { $op = $op2[[int]$il[$i]]; $i++ } else { $op = $op1[[int]$b] }
        if (-not $op) { $script:protectedIL++; break }   # undecodable -> encrypted/obfuscated body
        switch ($op.OperandType.ToString()) {
            'InlineNone' { }
            { $_ -in 'ShortInlineBrTarget', 'ShortInlineI', 'ShortInlineVar' } { $i += 1 }
            'InlineVar' { $i += 2 }
            'InlineI8' { $i += 8 }
            'InlineR' { [pscustomobject]@{ Kind = 'const'; Target = [BitConverter]::ToDouble($il, $i) }; $i += 8 }
            'ShortInlineR' { [pscustomobject]@{ Kind = 'const'; Target = [BitConverter]::ToSingle($il, $i) }; $i += 4 }
            'InlineSwitch' { $n = [BitConverter]::ToInt32($il, $i); $i += 4 + 4 * $n }
            default {
                $tok = [BitConverter]::ToInt32($il, $i); $i += 4
                try {
                    switch ($op.OperandType.ToString()) {
                        'InlineMethod' { [pscustomobject]@{ Kind = 'call';  Target = $mod.ResolveMethod($tok, $tArgs, $mArgs) } }
                        'InlineField'  { [pscustomobject]@{ Kind = 'field'; Target = $mod.ResolveField($tok, $tArgs, $mArgs) } }
                        'InlineString' { [pscustomobject]@{ Kind = 'str';   Target = $mod.ResolveString($tok) } }
                    }
                } catch {}
            }
        }
    }
}

$orderRx = '^(Enter|Exit)(Long|Short)|^SubmitOrderUnmanaged$|^ChangeOrder$|^CancelOrder$|^Set(StopLoss|ProfitTarget|TrailStop)$|^CloseStrategy$'
$flags   = [Reflection.BindingFlags]'Public,NonPublic,Instance,Static,DeclaredOnly'

function Short([Reflection.MemberInfo]$x) { if ($x.DeclaringType) { "$($x.DeclaringType.Name).$($x.Name)" } else { $x.Name } }

function Show-Tree([Reflection.MethodBase]$m, [int]$depth, $seen) {
    $pad = '  ' * $depth
    $key = $m.DeclaringType.FullName + '::' + $m.ToString()
    if (-not $seen.Add($key)) { W "$pad$(Short $m)  (see above)"; return }
    $refs = @(Get-ILRefs $m)
    W "$pad$(Short $m)"
    $uses = [ordered]@{}; $state = [ordered]@{}; $props = [ordered]@{}; $consts = [ordered]@{}; $strs = [ordered]@{}; $children = [ordered]@{}
    foreach ($r in $refs) {
        $t = $r.Target
        switch ($r.Kind) {
            'const' { $consts["$t"] = 1 }
            'field' {
                if ($t.Module.Assembly -eq $asm) { if ($t.Name -notmatch 'k__BackingField|^<>') { $state[$t.Name] = 1 } }
                elseif ($t.DeclaringType -and $t.DeclaringType.Namespace -like 'NinjaTrader*') { $uses[$t.Name] = 1 }
            }
            'str'   { if ($t.Length -gt 60) { $t = $t.Substring(0, 57) + '...' }; $strs["`"$t`""] = 1 }
            'call'  {
                if ($t.Name -match $orderRx) { W "$pad    >> ORDER: $(Short $t)$('(' + (($t.GetParameters() | ForEach-Object { $_.Name }) -join ', ') + ')')" }
                elseif ($t.Module.Assembly -eq $asm) {
                    if ($t.Name -match '^(get|set)_') { $props[$t.Name.Substring(4)] = 1 }
                    else { $children[$t.DeclaringType.FullName + '::' + $t.ToString()] = $t }
                }
                elseif ($t.DeclaringType -and $t.DeclaringType.Namespace -like 'NinjaTrader*') { $uses[($t.Name -replace '^(get|set)_', '')] = 1 }
            }
        }
    }
    if ($props.Count)  { W "$pad    props:  $($props.Keys -join ', ')" }
    if ($state.Count)  { W "$pad    state:  $($state.Keys -join ', ')" }
    if ($uses.Count)   { W "$pad    NT API: $($uses.Keys -join ', ')" }
    if ($consts.Count) { W "$pad    consts: $($consts.Keys -join ', ')" }
    if ($strs.Count)   { W "$pad    strs:   $($strs.Keys -join ', ')" }
    if ($depth -ge $MaxDepth) { if ($children.Count) { W "$pad    ... (max depth)" }; return }
    foreach ($c in $children.Values) { Show-Tree $c ($depth + 1) $seen }
}

# --- Report ---
W "Assembly : $($asm.Location)"
W "Version  : $($asm.GetName().Version)"
W "Targets  : $(($targets | ForEach-Object FullName) -join ', ')"
W "Scope    : $($scopeTypes.Count) type(s)$(if ($isVendorDll) { ' (vendor DLL, all types)' })"
W

W '=== 1. PARAMETERS (what the user can configure) ==='
foreach ($t in $targets) {
    foreach ($p in $t.GetProperties($flags)) {
        $attrs = @($p.GetCustomAttributesData() | Where-Object { $_.AttributeType.Name -match 'NinjaScriptProperty|Display|Range|XmlIgnore|Browsable' })
        if (-not $attrs) { continue }
        $desc = $attrs | ForEach-Object {
            $a = ($_.ConstructorArguments | ForEach-Object { "$($_.Value)" }) + ($_.NamedArguments | ForEach-Object { "$($_.MemberName)=$($_.TypedValue.Value)" })
            "$($_.AttributeType.Name -replace 'Attribute$')($($a -join ', '))"
        }
        W ("  {0,-32} {1,-12} {2}" -f $p.Name, $p.PropertyType.Name, ($desc -join ' '))
    }
}
W

W '=== 2. CALL TREES FROM EVENT HANDLERS (signal/scanner flow) ==='
$seen = [System.Collections.Generic.HashSet[string]]::new()
foreach ($t in $targets) {
    foreach ($h in ($t.GetMethods($flags) | Where-Object { $_.Name -like 'On*' } | Sort-Object Name)) {
        W; Show-Tree $h 0 $seen
    }
}
# Anything in scope that places orders but was not reached from a handler (timers, threads, callbacks)
$orphans = foreach ($t in $scopeTypes) {
    foreach ($m in $t.GetMethods($flags)) {
        $k = $m.DeclaringType.FullName + '::' + $m.ToString()
        if (-not $seen.Contains($k) -and (Get-ILRefs $m | Where-Object { $_.Kind -eq 'call' -and $_.Target.Name -match $orderRx })) { $m }
    }
}
if ($orphans) { W; W '--- Order-placing methods not reached from an On* handler ---'; foreach ($m in $orphans) { W; Show-Tree $m 0 $seen } }
W

W '=== 3. MEMBER DUMP ==='
foreach ($t in $scopeTypes) {
    W; W "== $($t.FullName) : $($t.BaseType)"
    foreach ($f in $t.GetFields($flags))     { W ("  field  {0,-30} {1}" -f $f.FieldType.Name, $f.Name) }
    foreach ($p in $t.GetProperties($flags)) { W ("  prop   {0,-30} {1}" -f $p.PropertyType.Name, $p.Name) }
    foreach ($m in @($t.GetConstructors($flags)) + @($t.GetMethods($flags))) {
        $size = try { $m.GetMethodBody().GetILAsByteArray().Length } catch { '?' }
        W ("  method IL={0,-6} {1}" -f $size, $m)
    }
}

if ($script:protectedIL) {
    W; W "NOTE: $($script:protectedIL) method bodies could not be decoded - the assembly looks protected/obfuscated. Signatures above are still accurate; call trees will be incomplete."
}

$lines | Set-Content -Path $OutFile -Encoding UTF8
Write-Host "Wrote $($lines.Count) lines to $OutFile"
