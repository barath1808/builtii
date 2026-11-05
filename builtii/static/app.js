const form=document.getElementById('upload'),button=document.getElementById('submit'),error=document.getElementById('error');
let timer;
function fail(message){error.textContent=message;error.hidden=false;button.disabled=false;clearTimeout(timer);}
async function poll(id){
  try{
    const response=await fetch('/api/jobs/'+encodeURIComponent(id));
    if(!response.ok)throw new Error('Cannot read job status.');
    const job=await response.json();
    document.getElementById('progress').hidden=false;
    document.getElementById('state').textContent=job.state.replaceAll('_',' ');
    document.getElementById('message').textContent=job.message||'Waiting';
    const bar=document.getElementById('bar');bar.max=job.total||1;bar.value=job.done;
    if(['completed','incomplete'].includes(job.state)){
      const link=document.getElementById('report');link.href='/jobs/'+id+'/report.html';link.hidden=false;button.disabled=false;sessionStorage.removeItem('builtiiJob');return;
    }
    if(['failed','interrupted'].includes(job.state)){sessionStorage.removeItem('builtiiJob');fail(job.message);return;}
    timer=setTimeout(()=>poll(id),2000);
  }catch(e){fail(e.message+' Reload this page to reconnect to the job.');}
}
form.addEventListener('submit',async event=>{
  event.preventDefault();error.hidden=true;document.getElementById('report').hidden=true;
  const file=document.getElementById('pdf').files[0];
  if(!file||file.size>100*1024*1024){fail('Choose a PDF up to 100 MiB.');return;}
  button.disabled=true;
  try{
    const response=await fetch('/api/jobs',{method:'POST',body:new FormData(form)});
    const result=await response.json();if(!response.ok)throw new Error(typeof result.detail==='string'?result.detail:'Upload failed.');
    sessionStorage.setItem('builtiiJob',result.id);poll(result.id);
  }catch(e){fail(e.message);}
});
const previous=sessionStorage.getItem('builtiiJob');if(previous){button.disabled=true;poll(previous);}
