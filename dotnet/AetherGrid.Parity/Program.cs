using System.Text.Json;
using AetherGrid.Core;
var fixtures=JsonDocument.Parse(File.ReadAllText(args[0]));var checks=0;
void Near(double a,double b,string label){if(Math.Abs(a-b)>1e-8*Math.Max(1,Math.Abs(b)))throw new Exception($"{label}: {a} != {b}");checks++;}
foreach(var c in fixtures.RootElement.GetProperty("bio").EnumerateArray())
{
    var p=c.GetProperty("profile");var timer=new BioTimer(new(p.GetProperty("shelf_hours_ref").GetDouble(),p.GetProperty("q10").GetDouble(),p.GetProperty("opt_temp_c").GetDouble(),p.GetProperty("max_safe_temp_c").GetDouble(),p.GetProperty("eth_sensitivity").GetDouble(),p.GetProperty("wholesale_price_inr_per_kg").GetDouble()));
    foreach(var row in c.GetProperty("intervals").EnumerateArray())
    {var v=row.EnumerateArray().ToArray();timer.Apply(v[0].GetDouble(),v[1].GetDouble(),v[2].GetDouble(),v[3].GetDouble(),v[4].GetBoolean());}
    var q=c.GetProperty("query").EnumerateArray().Select(v=>v.GetDouble()).ToArray();var got=timer.Snapshot(q[0],q[1],q[2],q[3]);var e=c.GetProperty("expected");
    Near(got.LifeConsumed,e.GetProperty("life").GetDouble(),"life");Near(got.Rvh,e.GetProperty("rvh").GetDouble(),"rvh");Near(got.SpoilEta,e.GetProperty("eta").GetDouble(),"eta");Near(got.DecayRate,e.GetProperty("rate").GetDouble(),"rate");Near(timer.HoursOutOfRange,e.GetProperty("oor").GetDouble(),"oor");
    if(got.Health!=e.GetProperty("health").GetString())throw new Exception("Health mismatch");checks++;
    var t=e.GetProperty("ttd");if(t.ValueKind==JsonValueKind.Null){if(got.TimeToDistress!=null)throw new Exception("TTD not null");checks++;}else Near(got.TimeToDistress??-1,t.GetDouble(),"ttd");
}
foreach(var c in fixtures.RootElement.GetProperty("settlements").EnumerateArray())
{
    var i=JsonSerializer.Deserialize<SettlementInput>(c.GetProperty("input").GetRawText())!;var got=Settlement.Compute(i);var e=c.GetProperty("expected");
    // Python API outputs monetary values rounded to two decimals.
    Near(Math.Round(got.Farmer,2),e.GetProperty("farmer").GetDouble(),"farmer");Near(Math.Round(got.Insurance,2),e.GetProperty("insurance").GetDouble(),"insurance");Near(Math.Round(got.Penalty,2),e.GetProperty("penalty").GetDouble(),"penalty");Near(Math.Round(got.RecoveryPct,2),e.GetProperty("recovery").GetDouble(),"recovery");
}
foreach(var c in fixtures.RootElement.GetProperty("eligibility").EnumerateArray())
{
    var input=JsonSerializer.Deserialize<EligibilityInput>(c.GetProperty("input").GetRawText())!;
    var expected=c.GetProperty("expected").EnumerateArray().Select(x=>x.GetString()).ToArray();
    if(!Eligibility.Reject(input).SequenceEqual(expected))throw new Exception("Eligibility mismatch");checks++;
}
Console.WriteLine(JsonSerializer.Serialize(new {passed=true,checks,eligibility_cases=fixtures.RootElement.GetProperty("eligibility").GetArrayLength(),bio_cases=fixtures.RootElement.GetProperty("bio").GetArrayLength(),settlement_cases=fixtures.RootElement.GetProperty("settlements").GetArrayLength()}));
