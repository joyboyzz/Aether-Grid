namespace AetherGrid.Core;
public record SettlementInput(double Wholesale,double WeightKg,double ContractValue,double? SumAssured,double Cover,double Deductible,double BidPrice,double ClearedKg,double LifePct,double HoursOutOfRange,int DoorEvents,double Sla,double PenaltyMultiplier=2,double Floor=.7);
public record SettlementResult(double Salvage,double Insurance,double Penalty,double Farmer,double RecoveryPct,double BuyerSavingsPct,double Topup);
public static class Settlement
{
    // Full precision parity values. Currency rail boundaries must use integer paise.
    public static SettlementResult Compute(SettlementInput p)
    {
        if(new[]{p.Wholesale,p.WeightKg,p.ContractValue,p.SumAssured??0,p.Cover,p.Deductible,p.BidPrice,p.ClearedKg,p.LifePct,p.HoursOutOfRange,p.Sla,p.PenaltyMultiplier,p.Floor}.Any(v=>!double.IsFinite(v))||p.Wholesale<=0||p.ContractValue<=0||p.SumAssured<0||p.LifePct<0||p.LifePct>150||p.HoursOutOfRange<0||p.DoorEvents<0||p.Sla<0||p.Sla>100||p.Floor<0||p.Floor>1||p.PenaltyMultiplier<0)throw new ArgumentException("Invalid settlement parameters");
        if(p.WeightKg<=0||p.ClearedKg<=0||p.ClearedKg>p.WeightKg||p.BidPrice<=0||p.Cover<0||p.Cover>1||p.Deductible<0||p.Deductible>1)throw new ArgumentException("Invalid settlement");
        var expected=p.Wholesale*p.WeightKg;var salvage=p.BidPrice*p.ClearedKg;
        var assured=p.SumAssured is null or 0?p.ContractValue*.5:p.SumAssured.Value;
        var insurance=Math.Min(Math.Max(0,expected-salvage),assured*p.Cover)*(1-p.Deductible);
        var sla=Math.Max(.2,(100-p.Sla)/20+1);
        var abuse=p.LifePct/100*(1+p.HoursOutOfRange/24)*(p.DoorEvents==0?1:1.2);
        var penalty=Math.Min(p.ContractValue*.05*abuse*sla*p.PenaltyMultiplier,p.ContractValue*.30);
        var topup=Math.Min(Math.Max(0,p.Floor*expected-salvage-insurance),penalty);
        var farmer=salvage+insurance+topup;
        return new(salvage,insurance,penalty,farmer,farmer/Math.Max(1,expected)*100,Math.Max(0,(p.Wholesale-p.BidPrice)/p.Wholesale*100),topup);
    }
}
