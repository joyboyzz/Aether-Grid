namespace AetherGrid.Core;
public record EligibilityInput(string Commodity,double LotKg,double RequestedKg,double Price,double CapacityKg,string[] AcceptedCommodities,double EscrowInr,double DistanceKm,double ServiceRadiusKm,double RescueRadiusKm,double RvhHours,bool Approved,bool Expired=false);
public static class Eligibility
{
    public static string[] Reject(EligibilityInput p)
    {
        if(new[]{p.LotKg,p.RequestedKg,p.Price,p.CapacityKg,p.EscrowInr,p.DistanceKm,p.ServiceRadiusKm,p.RescueRadiusKm,p.RvhHours}.Any(v=>!double.IsFinite(v)))return ["non_finite_or_missing_input"];
        var reasons=new List<string>();
        if(p.Expired)reasons.Add("auction_expired");
        if(!p.Approved)reasons.Add("policy_not_pre_authorized");
        if(!p.AcceptedCommodities.Contains(p.Commodity))reasons.Add("commodity_mismatch");
        if(p.LotKg<=0||Math.Abs(p.RequestedKg-p.LotKg)>.001)reasons.Add("full_lot_required");
        if(p.RequestedKg>p.CapacityKg)reasons.Add("insufficient_capacity");
        if(p.Price<=0||p.EscrowInr<p.Price*p.RequestedKg)reasons.Add("insufficient_simulated_escrow");
        if(p.DistanceKm<0||p.DistanceKm>Math.Min(p.ServiceRadiusKm,p.RescueRadiusKm))reasons.Add("outside_radius");
        if(p.RvhHours<=0||p.DistanceKm/30+.25>=p.RvhHours)reasons.Add("unreachable_before_rvh");
        return reasons.ToArray();
    }
}
