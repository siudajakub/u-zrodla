// Dependency-free render smoke test for the built, offline React desk.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('web/app.js', 'utf8');
function render(data) {
  let index = 0, output;
  const React = {
    createElement(type, props) { return typeof type === 'function' ? type(props) : props; },
    useState(initial) { return [index++ === 0 ? data : initial, () => {}]; },
    useRef(value) { return {current:value}; },
    useEffect() {}, useCallback(fn) { return fn; },
  };
  const context = {React, ReactDOM:{createRoot(){return {render(v){output=v}}}},
    document:{getElementById(){return {}}}, location:{origin:'http://localhost',protocol:'http:',host:'localhost'},
    URL, URLSearchParams, setTimeout, clearTimeout, console};
  vm.runInNewContext(source, context);
  return output.dangerouslySetInnerHTML.__html;
}
const empty = render({findings:[],creators:[],sources:[],scans:[]});
assert.match(empty, /Brak materiałów dla wybranych filtrów/);
const populated = render({creators:[{id:'c',name:'Autor',platform:'YouTube'}],sources:[],scans:[],findings:[{
  id:'f',creatorId:'c',title:'<script>alert(1)</script>',module:'M1',platform:'YouTube',score:75,
  summary:'Materiał',mediaUrl:'/media/studio.mp4',evidence:[{kind:'audio',start:7,text:'Partnerstwo'}],status:'new'
}]});
assert.match(populated, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
assert.doesNotMatch(populated, /<script>alert/);
assert.match(populated, /data-start="7"/);
assert.match(populated, /Autor/);
assert.match(populated, /<video/);
console.log('render smoke: empty queue, escaped source text and timed evidence OK');
