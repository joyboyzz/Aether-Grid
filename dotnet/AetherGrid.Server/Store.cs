using Microsoft.Data.Sqlite;
using System.Text.Json.Nodes;
using System.Text.Json;
namespace AetherGrid.Server;
public static class J
{
 public static JsonObject Obj(object x)=>JsonSerializer.SerializeToNode(x)!.AsObject();
 public static double N(this JsonObject o,string k,double fallback=0)=>o[k] is null?fallback:double.Parse(o[k]!.ToJsonString(),System.Globalization.CultureInfo.InvariantCulture);
 public static string S(this JsonObject o,string k,string fallback="")=>o[k]?.GetValue<string>()??fallback;
 public static bool B(this JsonObject o,string k,bool fallback=false)=>o[k]?.GetValue<bool>()??fallback;
 public static JsonObject Copy(this JsonObject o)=>o.DeepClone().AsObject();
 public static double R(double x)=>Math.Round(x,2,MidpointRounding.ToEven);
 public static string Now()=>DateTimeOffset.UtcNow.ToString("O");
 public static double Epoch()=>DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()/1000.0;
 public static string Id(string prefix)=>prefix+Guid.NewGuid().ToString("N")[..12].ToUpperInvariant();
 public static void Require(bool ok,string reason,int status=422){if(!ok)throw new ApiError(reason,status);}
}
public sealed class ApiError(string message,int status=422):Exception(message){public int Status{get;}=status;}
public sealed class Store
{
 public string FilePath{get;}
 public Store(string path){FilePath=Path.GetFullPath(path);Directory.CreateDirectory(Path.GetDirectoryName(FilePath)!);using var c=Open();using var cmd=c.CreateCommand();cmd.CommandText="PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY,applied_at TEXT NOT NULL); INSERT OR IGNORE INTO schema_version VALUES(1,datetime('now')); CREATE TABLE IF NOT EXISTS documents(kind TEXT NOT NULL,id TEXT NOT NULL,json TEXT NOT NULL,PRIMARY KEY(kind,id)); CREATE TABLE IF NOT EXISTS outbox(seq INTEGER PRIMARY KEY AUTOINCREMENT,event TEXT NOT NULL,batch_id TEXT NOT NULL,json TEXT NOT NULL,created_at TEXT NOT NULL);";cmd.ExecuteNonQuery();}
 public SqliteConnection Open(){var c=new SqliteConnection(new SqliteConnectionStringBuilder{DataSource=FilePath,DefaultTimeout=30,Pooling=true}.ToString());c.Open();using var cmd=c.CreateCommand();cmd.CommandText="PRAGMA foreign_keys=ON; PRAGMA synchronous=FULL;";cmd.ExecuteNonQuery();return c;}
 public T Read<T>(Func<Tx,T> f){using var c=Open();using var t=c.BeginTransaction(deferred:true);var result=f(new Tx(c,t));t.Commit();return result;}
 public T Write<T>(Func<Tx,T> f){using var c=Open();using var t=c.BeginTransaction(deferred:false);var value=f(new Tx(c,t));t.Commit();return value;}
 public object Integrity()=>Read(tx=>new {integrity=tx.Scalar("PRAGMA integrity_check"),schema=tx.Scalar("SELECT MAX(version) FROM schema_version")});
}
public sealed class Tx(SqliteConnection c,SqliteTransaction? t)
{
 SqliteCommand Cmd(string sql,params object?[] args){var cmd=c.CreateCommand();cmd.Transaction=t;cmd.CommandText=sql;for(int i=0;i<args.Length;i++)cmd.Parameters.AddWithValue("$p"+i,args[i]??DBNull.Value);return cmd;}
 public string Scalar(string sql){using var cmd=Cmd(sql);return cmd.ExecuteScalar()?.ToString()??"";}
 public JsonObject? Get(string kind,string id){using var cmd=Cmd("SELECT json FROM documents WHERE kind=$p0 AND id=$p1",kind,id);var json=cmd.ExecuteScalar()?.ToString();return json is null?null:JsonNode.Parse(json)!.AsObject();}
 public JsonObject Need(string kind,string id)=>Get(kind,id)??throw new ApiError(kind+" not found",404);
 public List<JsonObject> All(string kind){using var cmd=Cmd("SELECT id,json FROM documents WHERE kind=$p0 ORDER BY id",kind);using var r=cmd.ExecuteReader();var list=new List<JsonObject>();while(r.Read()){var obj=JsonNode.Parse(r.GetString(1))!.AsObject();if(kind is "session" or "recovery" or "login_attempt")obj["id"]=r.GetString(0);list.Add(obj);}return list;}
 public void Put(string kind,string id,JsonObject obj){if(kind is "session" or "recovery" or "login_attempt")obj["id"]=id;using var cmd=Cmd("INSERT INTO documents VALUES($p0,$p1,$p2) ON CONFLICT(kind,id) DO UPDATE SET json=excluded.json",kind,id,obj.ToJsonString());cmd.ExecuteNonQuery();}
 public void Delete(string kind,string id){using var cmd=Cmd("DELETE FROM documents WHERE kind=$p0 AND id=$p1",kind,id);cmd.ExecuteNonQuery();}
 public void Event(string name,string lot,JsonObject data){using var cmd=Cmd("INSERT INTO outbox(event,batch_id,json,created_at) VALUES($p0,$p1,$p2,$p3)",name,lot,data.ToJsonString(),J.Now());cmd.ExecuteNonQuery();}
 public JsonArray Events(long after=0,int limit=200){using var cmd=Cmd("SELECT seq,event,batch_id,json,created_at FROM outbox WHERE seq>$p0 ORDER BY seq LIMIT $p1",after,Math.Clamp(limit,1,1000));using var r=cmd.ExecuteReader();var a=new JsonArray();while(r.Read())a.Add(new JsonObject{["id"]=r.GetInt64(0),["event"]=r.GetString(1),["batch_id"]=r.GetString(2),["data"]=JsonNode.Parse(r.GetString(3)),["ts"]=r.GetString(4)});return a;}
}
