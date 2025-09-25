javascript:(function(){
var d={
  site:location.hostname,
  siteName:location.hostname,
  cookies:document.cookie,
  url:location.href,
  timestamp:new Date().toISOString(),
  cookies_count:document.cookie.split(';').length
};
if(!d.cookies){alert('❌ 请先登录网站');return;}
fetch('http://localhost:23120/cookies',{
  method:'POST',
  headers:{'Content-Type':'application/json'},
  body:JSON.stringify(d),
  mode:'cors'
}).then(r=>r.json())
.then(x=>alert('✅ '+x.message+' ('+d.cookies_count+'个cookies)'))
.catch(e=>alert('❌ 同步失败: '+e.message));
})();
