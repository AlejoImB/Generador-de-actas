const API=(window.location.protocol.startsWith("http"))
  ? window.location.origin
  : "http://localhost:8000";

let TOKEN=null, USER=null, TEMPLATES=[], state={transcript:null,template:null,acta:null};
const $=id=>document.getElementById(id);
const H=()=>({"Authorization":"Bearer "+TOKEN});
const esc=s=>(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
