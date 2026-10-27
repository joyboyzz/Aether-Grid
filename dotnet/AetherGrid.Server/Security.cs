using System.Security.Cryptography;
using System.Text;
using System.Text.Json.Nodes;
namespace AetherGrid.Server;
public record Actor(string Subject,string Role,string BuyerId="",string TruckId="",string? SessionId=null,string? Csrf=null);
public sealed class Security(Store store,IConfiguration config)
{
 private static readonly string DummyHash=Password("dummy-password-not-an-account");
 public bool SecureCookies=>config["AETHER_PRODUCTION"]=="true";
 public static string Hash(string text)=>Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(text))).ToLowerInvariant();
 public static bool Same(string a,string b)=>CryptographicOperations.FixedTimeEquals(SHA256.HashData(Encoding.UTF8.GetBytes(a)),SHA256.HashData(Encoding.UTF8.GetBytes(b)));
 public static string Random()=>Convert.ToHexString(RandomNumberGenerator.GetBytes(32)).ToLowerInvariant();
 public static string Password(string value){var salt=RandomNumberGenerator.GetBytes(16);var hash=Rfc2898DeriveBytes.Pbkdf2(value,salt,210000,HashAlgorithmName.SHA256,32);return "pbkdf2-sha256$210000$"+Convert.ToBase64String(salt)+"$"+Convert.ToBase64String(hash);}
 public static bool ValidHash(string encoded){try{var p=encoded.Split('$');return p.Length==4&&p[0]=="pbkdf2-sha256"&&int.Parse(p[1]) is >=210000 and <=1000000&&Convert.FromBase64String(p[2]).Length>=16&&Convert.FromBase64String(p[3]).Length==32;}catch{return false;}}
 public static bool Verify(string password,string encoded){try{var p=encoded.Split('$');if(p[0]!="pbkdf2-sha256"||p.Length!=4)return false;var rounds=int.Parse(p[1]);if(rounds<210000||rounds>1000000)return false;return CryptographicOperations.FixedTimeEquals(Rfc2898DeriveBytes.Pbkdf2(password,Convert.FromBase64String(p[2]),rounds,HashAlgorithmName.SHA256,32),Convert.FromBase64String(p[3]));}catch{return false;}}
 public void Bootstrap(){var file=config["AETHER_USERS_FILE"];if(string.IsNullOrEmpty(file))return;var users=JsonNode.Parse(File.ReadAllText(file))!.AsArray();store.Write(tx=>{foreach(var node in users){var u=node!.AsObject();J.Require(u.S("username").Length>=3&&ValidHash(u.S("password_hash")),"Invalid bootstrap user");J.Require(new[]{"operator","auditor","buyer"}.Contains(u.S("role")),"Invalid role");J.Require(u.S("role")!="buyer"||u.S("buyer_id").Length>=3,"Buyer identity binding required");var old=tx.Get("user",u.S("username"));if(old is null){u["version"]=1;u["disabled"]=false;tx.Put("user",u.S("username"),u);}}return true;});}
 public Actor? Identify(HttpContext ctx)
 {
  var bearer=ctx.Request.Headers.Authorization.ToString();
  if(bearer.StartsWith("Bearer ")){var key=store.Read(tx=>tx.Get("api_key",Hash(bearer[7..])));if(key is null||key.B("disabled")||key.N("expires_at")<=J.Epoch())return null;return new(key.S("subject"),key.S("role"),key.S("buyer_id"),key.S("truck_id"));}
  var token=ctx.Request.Cookies["ag_session"];if(token is null)return null;return store.Read(tx=>{var id=Hash(token);var s=tx.Get("session",id);if(s is null||s.N("expires_at")<=J.Epoch())return null;var u=tx.Get("user",s.S("username"));if(u is null||u.B("disabled")||u.N("version")!=s.N("version"))return null;return new Actor(u.S("username"),u.S("role"),u.S("buyer_id"),"",id,s.S("csrf"));});
 }
 public object Login(HttpContext ctx,JsonObject body)
 {
  var username=body.S("username");var password=body.S("password");J.Require(username.Length<=120&&password.Length<=1024,"Invalid credentials",401);
  var token=Random();var csrf=Random();var expiry=J.Epoch()+8*3600;
  var actor=store.Write(tx=>{var bucket=Hash((ctx.Connection.RemoteIpAddress?.ToString()??"unknown")+"|"+username);var counter=tx.Get("login_attempt",bucket);if(counter is not null&&counter.N("locked_until")>J.Epoch())throw new ApiError("Try later",429);var u=tx.Get("user",username);var valid=Verify(password,u?.S("password_hash")??DummyHash);if(u is null||u.B("disabled")||!valid){counter??=new JsonObject{["count"]=0};counter["count"]=counter.N("count")+1;counter["updated_at"]=J.Epoch();if(counter.N("count")>=5){counter["locked_until"]=J.Epoch()+60;counter["count"]=0;}tx.Put("login_attempt",bucket,counter);return (Actor?)null;}tx.Delete("login_attempt",bucket);tx.Put("session",Hash(token),new JsonObject{["username"]=username,["version"]=u.N("version"),["csrf"]=csrf,["expires_at"]=expiry});tx.Event("login",username,new JsonObject{["subject"]=username});return new Actor(username,u.S("role"),u.S("buyer_id"),"",Hash(token),csrf);});
  if(actor is null)throw new ApiError("Invalid credentials",401);
  ctx.Response.Cookies.Append("ag_session",token,new CookieOptions{HttpOnly=true,Secure=SecureCookies,SameSite=SameSiteMode.Strict,Path="/",MaxAge=TimeSpan.FromHours(8),IsEssential=true});return Session(actor);
 }
 public object Session(Actor actor)=>new {authenticated=true,subject=actor.Subject,role=actor.Role,buyer_id=actor.BuyerId,csrf=actor.Csrf,transport=actor.Role=="operator"?"sse":"poll"};
 public void Logout(HttpContext ctx,Actor actor){if(actor.SessionId is not null)store.Write(tx=>{tx.Delete("session",actor.SessionId);return true;});ctx.Response.Cookies.Delete("ag_session",new CookieOptions{Path="/",Secure=SecureCookies,SameSite=SameSiteMode.Strict});}
 public static Actor Actor(HttpContext ctx)=>(Actor)ctx.Items["actor"]!;
 public static void Operator(HttpContext ctx)=>J.Require(Actor(ctx).Role=="operator","Operator required",403);
 public static void Review(HttpContext ctx,JsonObject body){Operator(ctx);J.Require(body.B("simulated_escrow_acknowledged"),"Explicit simulation acknowledgement required");}
}
