import { INPUT, OUTPUT, REPORT } from './paths.js';
const RAW = ["Cedarbyte", "audit.person@example.invalid", "+1 202-555-0199"];
let sawRead=false, sawWrite=false, sawEdit=false, captured=[], writtenContent="";
function result(e, answer, tools=[], stop="end_turn") { return {turnId:e.turnId,index:e.index,answer,toolUses:tools,stopReason:stop,usage:null}; }
function facts(messages) { const data=JSON.stringify(messages); return {array:Array.isArray(messages),rawVisible:RAW.some(x=>data.includes(x)),hasCompanyAlias:data.includes("Harborwave"),hasEmailToken: /<PII_EMAIL_[A-Z0-9_]+>/.test(data),hasPhoneToken:/<PII_PHONE_[A-Z0-9_]+>/.test(data)}; }
export function register(on) {
  on("tool.call", async ($,e,next) => { if(e.tool==="Read")sawRead=true; if(e.tool==="Write")sawWrite=true; if(e.tool==="Edit")sawEdit=true; return next(e); });
  on("turn.step", async function*($,e) {
    const messages=await $.session.messages({as:"api"}); const data=JSON.stringify(messages); captured.push({index:e.index,...facts(messages)});
    let name, input;
    if(e.index===0){name="Read";input={file_path:INPUT};}
    else if(e.index===1){const email=data.match(/<PII_EMAIL_[A-Z0-9_]+>/)?.[0];const phone=data.match(/<PII_PHONE_[A-Z0-9_]+>/)?.[0];if(!email||!phone){await $.fs.write(REPORT,JSON.stringify({captured,sawRead,sawWrite,sawEdit,missingTokens:true}));yield {kind:"text",index:0,text:"AUDIT_MISSING_TOKENS"};return result(e,"AUDIT_MISSING_TOKENS");}name="Write";input={file_path:OUTPUT,content:`Synthetic output\nEmployer: Harborwave\nContact: ${email}\nPhone: ${phone}\nVersion: before\n`};}
    else if(e.index===2){name="Edit";input={file_path:OUTPUT,old_string:writtenContent,new_string:writtenContent.replace("Version: before","Version: after")};}
    else if(e.index===3){name="Read";input={file_path:OUTPUT};}
    else { await $.fs.write(REPORT,JSON.stringify({captured,sawRead,sawWrite,sawEdit,completed:true}));yield {kind:"text",index:0,text:"OFFLINE_MY_PRIVACY_AUDIT_COMPLETE"};yield {kind:"stop",stopReason:"end_turn",usage:null};return result(e,"OFFLINE_MY_PRIVACY_AUDIT_COMPLETE"); }
    if(name==="Write") writtenContent=input.content;
    yield {kind:"tool",index:0,id:`toolu_audit_${e.index}`,name};
    yield {kind:"input",index:0,json:JSON.stringify(input)};
    yield {kind:"stop",stopReason:"tool_use",usage:null};
    return result(e,"",[{name,input}],"tool_use");
  });
}
