using AetherGrid.Server;
using System.Text.Json.Nodes;
using System.Threading.RateLimiting;
var builder=WebApplication.CreateBuilder(args);
builder.WebHost.ConfigureKestrel(k=>k.Limits.MaxRequestBodySize=65536);
builder.Services.AddSingleton(new Store(builder.Configuration["AETHER_DB"]??"data/aethergrid.db"));
builder.Services.AddSingleton<Security>();builder.Services.AddSingleton<Workflow>();
builder.Services.AddRateLimiter(o=>{o.RejectionStatusCode=429;o.GlobalLimiter=PartitionedRateLimiter.Create<HttpContext,string>(ctx=>RateLimitPartition.GetFixedWindowLimiter(ctx.Connection.RemoteIpAddress?.ToString()??"unknown",_=>new FixedWindowRateLimiterOptions{PermitLimit=300,Window=TimeSpan.FromMinutes(1),QueueLimit=0}));o.AddPolicy("login",ctx=>RateLimitPartition.GetFixedWindowLimiter(ctx.Connection.RemoteIpAddress?.ToString()??"unknown",_=>new FixedWindowRateLimiterOptions{PermitLimit=10,Window=TimeSpan.FromMinutes(1),QueueLimit=0}));});
var app=builder.Build();var store=app.Services.GetRequiredService<Store>();var security=app.Services.GetRequiredService<Security>();var workflow=app.Services.GetRequiredService<Workflow>();
if((builder.Configuration["AETHER_TELEMETRY_ROOT"]??"").Length<32)throw new InvalidOperationException("Set AETHER_TELEMETRY_ROOT to at least 32 random characters; no built-in signing secret.");
security.Bootstrap();
app.Use(async(ctx,next)=>{ctx.Response.Headers["X-Content-Type-Options"]="nosniff";ctx.Response.Headers["Cache-Control"]="no-store";ctx.Response.Headers["Referrer-Policy"]="same-origin";try{await next();}catch(Exception e)when(e is ApiError or ArgumentException or InvalidOperationException or FormatException or System.Text.Json.JsonException){if(ctx.Response.HasStarted)throw;ctx.Response.StatusCode=e is ApiError a?a.Status:422;if(ctx.Request.Path=="/api/telemetry"&&ctx.Response.StatusCode==403)store.Write(tx=>{var m=tx.Get("metric","telemetry_rejections")??new JsonObject{["count"]=0};m["count"]=m.N("count")+1;tx.Put("metric","telemetry_rejections",m);tx.Event("telemetry_rejected","",new JsonObject{["description"]="Software signature or device-binding verification failed",["severity"]="warn"});return true;});await ctx.Response.WriteAsJsonAsync(new{detail=e is ApiError?e.Message:"Invalid request or state"});}});
app.UseRateLimiter();
app.Use(async(ctx,next)=>{
 var path=ctx.Request.Path.Value??"";if(!path.StartsWith("/api/")||path is "/api/health" or "/api/auth/login" or "/api/auth/recover"){await next();return;}
 var actor=security.Identify(ctx)??throw new ApiError("Authentication required",401);ctx.Items["actor"]=actor;
 if(actor.Role=="device")J.Require(path=="/api/telemetry"&&ctx.Request.Method=="POST","Device scope only",403);
 if(actor.Role=="buyer")J.Require(path.StartsWith("/api/auth/")||path.StartsWith("/api/auctions")||(path=="/api/buyers"||path=="/api/summary"||path=="/api/settlements"),"Buyer scope only",403);
 if(actor.Role=="auditor")J.Require(ctx.Request.Method=="GET"||(path=="/api/auth/logout"||path=="/api/auth/change-password"),"Read-only role",403);
 if(ctx.Request.Method!="GET"&&actor.SessionId is not null){J.Require(Security.Same(actor.Csrf??"",ctx.Request.Headers["X-CSRF-Token"].ToString()),"CSRF token required",403);var origin=ctx.Request.Headers.Origin.ToString();J.Require(string.IsNullOrEmpty(origin)||Uri.TryCreate(origin,UriKind.Absolute,out var u)&&u.Authority==ctx.Request.Host.Value,"Cross-origin mutation rejected",403);}
 await next();
});
app.MapGet("/api/health",()=>new{status="ok",backend="native-dotnet",mode="software-only-simulated",hardware=false,financial_execution=false});
app.MapPost("/api/auth/login",(HttpContext c,JsonObject p)=>security.Login(c,p)).RequireRateLimiting("login");
app.MapGet("/api/auth/session",(HttpContext c)=>security.Session(Security.Actor(c)));
app.MapPost("/api/auth/logout",(HttpContext c)=>{security.Logout(c,Security.Actor(c));return new{status="logged_out"};});
app.MapPost("/api/admin/provision",(HttpContext c,JsonObject p)=>{Security.Operator(c);return workflow.Provision(p,Security.Actor(c).Subject);});
app.MapPost("/api/admin/revoke-user/{id}",(HttpContext c,string id)=>{Security.Operator(c);return store.Write(tx=>{var u=tx.Need("user",id);u["version"]=u.N("version")+1;u["disabled"]=true;tx.Put("user",id,u);tx.Event("user_revoked",id,new JsonObject{["subject"]=Security.Actor(c).Subject});return new{status="revoked"};});});
app.MapPost("/api/batches/{id}/baseline",(HttpContext c,string id,JsonObject p)=>{Security.Operator(c);return workflow.Baseline(id,p,Security.Actor(c).Subject);});
app.MapPost("/api/batches/{id}/delivery",(HttpContext c,string id,JsonObject p)=>{Security.Operator(c);return workflow.Delivery(id,p,Security.Actor(c));});
app.MapPost("/api/telemetry",(HttpContext c,JsonObject p)=>workflow.Telemetry(p,Security.Actor(c)));
app.MapPost("/api/auctions/{id}/bid",(HttpContext c,string id,JsonObject p)=>workflow.Bid(id,p,Security.Actor(c)));
app.MapPost("/api/auctions/{id}/confirm",(HttpContext c,string id,JsonObject p)=>{Security.Review(c,p);return workflow.Confirm(id,p,Security.Actor(c));});
app.MapGet("/api/commodities",()=>workflow.Catalog["profiles"]!.AsObject().Select(p=>new{commodity=p.Key,profile=p.Value}));
app.MapGet("/api/batches",()=>store.Read(tx=>tx.All("batch")));
app.MapGet("/api/batches/{id}",(string id)=>store.Read(tx=>tx.Need("batch",id)));
app.MapPost("/api/routing/evaluate",(HttpContext c,JsonObject p)=>{Security.Operator(c);J.Require(p["buyers"] is JsonArray&&p["cold_storages"] is JsonArray,"Candidate arrays required");J.Require(p["buyers"]!.AsArray().Count<=100&&p["cold_storages"]!.AsArray().Count<=100,"Too many candidates");return new Routing(workflow).Ranked(p,p["buyers"]!.AsArray().Select(n=>n!.AsObject()),p["cold_storages"]!.AsArray().Select(n=>n!.AsObject()));});
app.MapGet("/api/batches/{id}/route-options",(string id)=>store.Read(tx=>new Routing(workflow).Operational(tx,tx.Need("batch",id))));
app.MapPost("/api/batches/{id}/route-decision",(HttpContext c,string id,JsonObject p)=>{Security.Operator(c);return store.Write(tx=>{var b=tx.Need("batch",id);J.Require(workflow.Active(b),"Lot is terminal",409);var options=new Routing(workflow).Operational(tx,b);var target=options.Select(n=>n!.AsObject()).FirstOrDefault(n=>n.S("target_id")==p.S("target_id")&&n.S("plan_type")==p.S("plan_type"))??throw new ApiError("Target no longer eligible",409);J.Require(p.S("evidence_note").Length>=20&&p.B("advisory_acknowledged"),"Review note and advisory acknowledgement required");b["routing_target"]=target.Copy();b["reroute_count"]=b.N("reroute_count")+1;tx.Put("batch",id,b);tx.Event("route_reviewed",id,new JsonObject{["target_id"]=target.S("target_id"),["subject"]=Security.Actor(c).Subject,["evidence_note"]=p.S("evidence_note"),["physical_dispatch"]=false});return new{status="model_route_selected",physical_dispatch=false,life_reset=false};});});
app.MapGet("/api/batches/{id}/route-plan",(string id)=>store.Read(tx=>new Routing(workflow).Plan(tx.Need("batch",id))));
app.MapGet("/api/batches/{id}/telemetry",(string id)=>store.Read(tx=>tx.All("sample").Where(s=>s.S("batch_id")==id).OrderBy(s=>s.N("seq")).TakeLast(500)));
app.MapGet("/api/buyers",(HttpContext c,double? lat,double? lng,double? radius)=>store.Read(tx=>tx.All("buyer").Where(b=>Security.Actor(c).Role!="buyer"||Security.Actor(c).BuyerId==b.S("id")).Where(b=>lat is null||lng is null||Workflow.Km(lat.Value,lng.Value,b.N("lat"),b.N("lng"))<=Math.Clamp(radius??50,1,500)).ToArray()));
app.MapGet("/api/auctions",(HttpContext c)=>store.Read(tx=>PortalScope.Auctions(tx,Security.Actor(c))));
app.MapGet("/api/settlements",(HttpContext c)=>store.Read(tx=>PortalScope.Settlements(tx,Security.Actor(c))));
app.MapGet("/api/carriers",()=>store.Read(tx=>tx.All("carrier")));
app.MapGet("/api/trucks",()=>store.Read(tx=>tx.All("truck")));
app.MapGet("/api/route",()=>new{nodes=workflow.Catalog["nodes"],edges=workflow.Catalog["edges"]!.AsArray().Select(e=>new{from=e!["from_node"],to=e["to_node"],km=e["distance_km"],speed=e["base_speed_kmh"],type=e["road_type"],coverage=e["cellular_coverage_pct"]}),corridor="Software route catalog",dead_zones=workflow.Catalog["dead_zones"]});
app.MapGet("/api/events",(string? batch_id)=>store.Read(tx=>tx.Events(0,1000).Where(n=>batch_id is null||n!["batch_id"]!.GetValue<string>()==batch_id).Reverse().Take(200).Select(n=>new{id=n!["id"],batch_id=n["batch_id"],ts=n["ts"],kind=n["event"],severity=n["data"]?["severity"]?.GetValue<string>()??"ok",description=n["data"]?["description"]?.GetValue<string>()??n["event"]!.GetValue<string>()})));
app.MapGet("/api/summary",(HttpContext c)=>store.Read(tx=>{var actor=Security.Actor(c);var batches=actor.Role=="buyer"?new List<JsonObject>():tx.All("batch");var settlements=PortalScope.Settlements(tx,actor);return new{active_trucks=actor.Role=="buyer"?0:tx.All("truck").Count,distressed=batches.Count(b=>b.S("status")=="DistressedLiquidation"),spoiled_total=batches.Count(b=>b.S("status")=="Spoiled"),rescued_total=settlements.Count,delivered=batches.Count(b=>b.S("status")=="Delivered"),spoof_rejections=actor.Role=="buyer"?0:tx.Get("metric","telemetry_rejections")?.N("count")??0,total_farmer_value_salvaged_inr=settlements.Sum(s=>s.N("farmer_total_payout_inr")),total_logistics_penalties_inr=settlements.Sum(s=>s.N("logistics_penalty_inr")),avg_buyer_savings_pct=settlements.Count==0?0:settlements.Average(s=>s.N("buyer_savings_pct")),active_auctions=PortalScope.Auctions(tx,actor).Count(a=>a.S("status")=="Open"),total_batches=batches.Count,active_batches=batches.Count(workflow.Active),distressed_batches=batches.Count(b=>b.S("status")=="DistressedLiquidation"),cleared_batches=settlements.Count,spoiled_batches=batches.Count(b=>b.S("status")=="Spoiled"),total_salvage_inr=settlements.Sum(s=>s.N("salvage_revenue_inr")),total_farmer_payout_inr=settlements.Sum(s=>s.N("farmer_total_payout_inr")),average_recovery_pct=settlements.Count==0?0:settlements.Average(s=>s.N("farmer_recovery_pct")),mode="simulated"};}));
app.MapGet("/api/admin/integrity",(HttpContext c)=>{Security.Operator(c);return store.Integrity();});
app.MapGet("/api/stream",async(HttpContext c)=>{
 Security.Operator(c);c.Response.ContentType="text/event-stream";c.Response.Headers["X-Accel-Buffering"]="no";long.TryParse(c.Request.Headers["Last-Event-ID"],out var cursor);if(long.TryParse(c.Request.Query["after"],out var query))cursor=Math.Max(cursor,query);
 while(!c.RequestAborted.IsCancellationRequested){if(security.Identify(c) is null)break;var events=store.Read(tx=>tx.Events(cursor,100));foreach(var node in events){var e=node!.AsObject();cursor=(long)e.N("id");await c.Response.WriteAsync($"id: {cursor}\nevent: {e.S("event")}\ndata: {e["data"]!.ToJsonString()}\n\n",c.RequestAborted);}await c.Response.WriteAsync(": heartbeat\n\n",c.RequestAborted);await c.Response.Body.FlushAsync(c.RequestAborted);await Task.Delay(1000,c.RequestAborted);}
});
Operations.Map(app,store,security,builder.Configuration);Providers.Map(app,store,builder.Configuration);Reporting.Map(app,store);
app.MapMethods("/api/{**path}",new[]{"GET","POST","PUT","DELETE","PATCH"},()=>Results.NotFound(new{detail="Unknown API endpoint"}));
app.UseDefaultFiles();app.UseStaticFiles();app.MapFallbackToFile("index.html");
var timer=new PeriodicTimer(TimeSpan.FromSeconds(1));var lifetime=app.Lifetime.ApplicationStopping;_=Task.Run(async()=>{try{while(await timer.WaitForNextTickAsync(lifetime)){try{workflow.Sweep();}catch(Exception ex){app.Logger.LogError(ex,"Auction sweep failed; persisted state retained");}}}catch(OperationCanceledException){}},lifetime);
app.Run();
