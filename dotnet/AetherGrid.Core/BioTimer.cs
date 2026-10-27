namespace AetherGrid.Core;

public record Commodity(double ShelfHoursRef,double Q10,double OptimalTemp,double MaxSafeTemp,double EthSensitivity,double Wholesale);
public record BioResult(double LifeConsumed,double Rvh,double SpoilEta,double DecayRate,string Health,double? TimeToDistress);
/// <summary>Python-compatible prototype heuristic. Not a calibrated food-safety model.</summary>
public sealed class BioTimer(Commodity profile)
{
    private readonly bool validProfile = Validate(profile);
    private static bool Validate(Commodity p)
    {
        if(new[]{p.ShelfHoursRef,p.Q10,p.OptimalTemp,p.MaxSafeTemp,p.EthSensitivity,p.Wholesale}.Any(v=>!double.IsFinite(v))||p.ShelfHoursRef<=0||p.Q10<=1||p.Q10>10||p.EthSensitivity<0||p.Wholesale<=0)throw new ArgumentException("Invalid commodity profile");return true;
    }
    public double LifeConsumed {get;private set;}
    public double HoursOutOfRange {get;private set;}
    public double MaxTemp {get;private set;}
    public double MaxEthylene {get;private set;}
    private double Temp(double t)=>Math.Pow(profile.Q10,(t-5)/10);
    private double Eth(double e)=>1+profile.EthSensitivity*Math.Log10(1+e/10);
    public static double Humidity(double h)=>h>=85 && h<=93 ? 1 : h<70 ? 1+(70-h)/70 : h>95 ? 1+(h-95)/30 : h<85 ? 1+(85-h)/200 : 1+(h-93)/60;
    public double Rate(double t,double h,double e)=>Temp(t)*Humidity(h)*Eth(e);
    public void Apply(double t,double h,double e,double hours,bool door=false)
    {
        if(!double.IsFinite(t)||!double.IsFinite(h)||!double.IsFinite(e)||!double.IsFinite(hours)||hours<0||e<0||h<0||h>100)throw new ArgumentException("Invalid interval");
        LifeConsumed=Math.Min(1.5,LifeConsumed+Rate(t,h,e)*(door?5:1)*hours/profile.ShelfHoursRef);
        HoursOutOfRange+= t>profile.MaxSafeTemp?hours:0;
        MaxTemp=Math.Max(MaxTemp,t);MaxEthylene=Math.Max(MaxEthylene,e);
    }
    public void Restore(double life,double hours,double maxTemp,double maxEthylene)
    {
        if(new[]{life,hours,maxTemp,maxEthylene}.Any(x=>!double.IsFinite(x))||life<0||life>1.5||hours<0)throw new ArgumentException("Invalid checkpoint");
        LifeConsumed=life;HoursOutOfRange=hours;MaxTemp=maxTemp;MaxEthylene=maxEthylene;
    }
    public string Health=>LifeConsumed<.35?"fresh":LifeConsumed<.65?"aging":LifeConsumed<.95?"critical":"spoiled";
    public double Optimistic()=>Math.Max(0,1-LifeConsumed)*profile.ShelfHoursRef/(Temp(profile.OptimalTemp)*Eth(.1));
    public double? TimeToDistress(double t,double h,double e,double ett,double panic)
    {
        var life=LifeConsumed;var eta=ett;var rate=Rate(t,h,e);const double step=5.0/60;
        for(var i=1;i<=288;i++)
        {
            life+=rate*step/profile.ShelfHoursRef;eta=Math.Max(0,eta-step);
            var remaining=Math.Max(0,1-life);var rvh=remaining>0?remaining*profile.ShelfHoursRef/rate:0;
            if(rvh<panic*eta||life>=1)return i*step;
        }
        return null;
    }
    public BioResult Snapshot(double t,double h,double e,double ett,double panic=3)
    {
        if(!double.IsFinite(t)||!double.IsFinite(h)||!double.IsFinite(e)||!double.IsFinite(ett)||h<0||h>100||e<0||ett<0)throw new ArgumentException("Invalid query");
        var rate=Rate(t,h,e);var remaining=Math.Max(0,1-LifeConsumed);
        return new(LifeConsumed,Optimistic(),remaining>0&&rate>0?remaining*profile.ShelfHoursRef/rate:0,rate,Health,TimeToDistress(t,h,e,ett,panic));
    }
}
