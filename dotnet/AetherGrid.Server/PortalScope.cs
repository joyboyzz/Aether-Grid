using System.Text.Json.Nodes;
namespace AetherGrid.Server;
public static class PortalScope
{
 public static List<JsonObject> Auctions(Tx tx,Actor actor){
  var buyers=tx.All("buyer");var mine=actor.Role=="buyer"?buyers.FirstOrDefault(b=>b.S("id")==actor.BuyerId):null;
  var result=new List<JsonObject>();
  foreach(var a in tx.All("auction")){
   var nearby=buyers.Where(b=>Workflow.Km(a.N("trigger_lat"),a.N("trigger_lng"),b.N("lat"),b.N("lng"))<=Math.Min(80,b.N("service_radius_km"))).ToArray();
   if(actor.Role=="buyer"){
    var won=a["bid"] is JsonObject bid&&bid.S("buyer_id")==actor.BuyerId;
    var open=a.S("status")=="Open"&&mine is not null&&nearby.Any(b=>b.S("id")==actor.BuyerId)&&mine.B("pre_authorized")&&mine["accepted_commodities"] is JsonArray accepted&&accepted.Any(c=>c!.GetValue<string>()==a.S("commodity"));
    if(!won&&!open)continue;
    nearby=nearby.Where(b=>b.S("id")==actor.BuyerId).ToArray();
   }
   a["nearby_buyers"]=new JsonArray(nearby.Select(b=>{var view=b.Copy();view["distance_km"]=Workflow.Km(a.N("trigger_lat"),a.N("trigger_lng"),b.N("lat"),b.N("lng"));return (JsonNode)view;}).ToArray());result.Add(a);
  }return result;
 }
 public static List<JsonObject> Settlements(Tx tx,Actor actor)=>tx.All("settlement").Where(s=>actor.Role!="buyer"||s.S("buyer_id")==actor.BuyerId).ToList();
}
