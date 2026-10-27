import { io } from "socket.io-client";
import { nativeBackend, transport } from "./auth";
type Handler = (...args:any[])=>void;
let socket: any = null;
export function getSocket(): any {
 if(socket)return socket;
 if(!nativeBackend){socket=io({path:"/socket.io",transports:["websocket","polling"]});return socket;}
 if(transport!=="sse"){socket={on(){return socket},off(){return socket},disconnect(){socket=null},connected:false};return socket;}
 const handlers=new Map<string,Set<Handler>>();
 const source=new EventSource("/api/stream");
 socket={on(name:string,fn:Handler){let set=handlers.get(name);if(!set){set=new Set();handlers.set(name,set);if(name!=="connect")source.addEventListener(name,(e)=>{const data=JSON.parse((e as MessageEvent).data);handlers.get(name)?.forEach(h=>h(data))});}set.add(fn);return socket;},off(name:string,fn?:Handler){if(fn)handlers.get(name)?.delete(fn);else handlers.get(name)?.clear();return socket;},disconnect(){source.close();socket=null;},connected:false};
 source.onopen=()=>{socket.connected=true;handlers.get("connect")?.forEach(h=>h())};
 source.onerror=()=>{socket.connected=false;handlers.get("disconnect")?.forEach(h=>h())};
 return socket;
}
