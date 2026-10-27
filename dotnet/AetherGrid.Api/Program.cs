using AetherGrid.Core;
using System.Security.Cryptography;
using System.Text;
var builder=WebApplication.CreateBuilder(args);var app=builder.Build();
var token=Environment.GetEnvironmentVariable("AETHER_DOTNET_TOKEN");
if(string.IsNullOrEmpty(token)||token.Length<32)throw new InvalidOperationException("Configure AETHER_DOTNET_TOKEN (32+ chars)");
app.Use(async(ctx,next)=>{
    if(ctx.Request.Path=="/healthz"){await next();return;}
    var candidate=ctx.Request.Headers.Authorization.ToString();
    var valid=candidate.StartsWith("Bearer ")&&CryptographicOperations.FixedTimeEquals(SHA256.HashData(Encoding.UTF8.GetBytes(candidate[7..])),SHA256.HashData(Encoding.UTF8.GetBytes(token)));
    if(!valid){ctx.Response.StatusCode=401;return;}await next();
});
app.MapGet("/healthz",()=>new {alive=true,scope="algorithm service; not full Python API parity"});
app.MapPost("/api/algorithm/settlement",(SettlementInput input)=>{try{return Results.Ok(Settlement.Compute(input));}catch(ArgumentException e){return Results.BadRequest(new{error=e.Message});}});
app.MapPost("/api/algorithm/bio",(BioRequest input)=>{
    try{if(input.Profile is null||input.Intervals is null||input.Query is null)throw new ArgumentException("Profile, intervals and query required");
    var timer=new BioTimer(input.Profile);foreach(var row in input.Intervals)timer.Apply(row.Temp,row.Humidity,row.Ethylene,row.Hours,row.Door);
    return Results.Ok(timer.Snapshot(input.Query.Temp,input.Query.Humidity,input.Query.Ethylene,input.Ett));}
    catch(ArgumentException e){return Results.BadRequest(new{error=e.Message});}
});
app.MapPost("/api/algorithm/eligibility",(EligibilityInput input)=>Results.Ok(new{reasons=Eligibility.Reject(input),simulated=true}));
app.Run();
record Interval(double Temp,double Humidity,double Ethylene,double Hours,bool Door=false);
record BioRequest(Commodity Profile,Interval[] Intervals,Interval Query,double Ett);
