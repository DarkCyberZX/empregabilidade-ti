// Painel interativo de vagas de TI para o visual HTML Content (edição normal, que executa scripts).
// A medida DAX "HTML Painel" entrega os dados na variável D; este código monta o painel e aplica os filtros escolhidos
// no próprio HTML (listas do cabeçalho ou clique nos gráficos), sem consultar o modelo de novo.
//   D.p [sk, plataforma]      D.n [sk, nível, vaga de entrada 1/0]      D.m [sk, modelo de trabalho]
//   D.v [sk, forma de contratação, informada 1/0]      D.u {UF: região} ('--' = sem UF)
//   D.c [sk, competência, 'T' técnica ou 'C' comportamental]
//   D.x vagas separadas por ';': plataforma, UF (2 letras), nível, modelo, contratação, marcadores (graduação 1,
//       diploma concluído 2, aceita cursando 4, inglês 8, menciona experiência 16) e as competências (2 caracteres cada);
//       números em base 36
// Regra dos filtros: cada gráfico mostra todas as categorias da própria dimensão (com a escolhida em destaque) e
// obedece aos demais filtros; os indicadores obedecem a todos. Competência escolhida: a lista e a matriz do mesmo tipo
// (técnica ou comportamental) mostram o ranking com ela em destaque; as do outro tipo mostram as vagas que a citam.
const root = (document.currentScript && document.currentScript.previousElementSibling) || Array.from(document.querySelectorAll('.pn')).pop();
const porSk = (lista, f) => { const a = []; lista.forEach(x => { a[x[0] - 1] = f(x); }); return a; };
const PLAT = porSk(D.p, x => x[1]);
const NIV = porSk(D.n, x => ({nome: x[1], ent: x[2] === 1}));
const MOD = porSk(D.m, x => x[1]);
const VIN = porSk(D.v, x => ({nome: x[1], inf: x[2] === 1}));
const COMP = porSk(D.c, x => ({nome: x[1], tec: x[2] === 'T'}));
const REG = D.u;
const MAPA = %%MAPA_JS%%;
const ORDEM_REGIAO = ['Norte', 'Nordeste', 'Centro-Oeste', 'Sudeste', 'Sul', 'Remoto / sem UF'];
const COR_MODELO = {'Presencial': '%%PRESENCIAL%%', 'Híbrido': '%%HIBRIDO%%', 'Remoto': '%%REMOTO%%'};
const GRUPOS = [[['Aprendiz', 'Estágio', 'Trainee'], 'Estágio/Trainee'], [['Júnior'], 'Júnior'], [['Pleno'], 'Pleno'], [['Sênior'], 'Sênior'], [['Especialista/Liderança'], 'Especialista'], [['Não informado'], 'Sem nível']];
const GRUPO_IX = GRUPOS.map(g => g[0].map(nome => NIV.findIndex(n => n && n.nome === nome)));

const R = D.x ? D.x.split(';') : [];
const N = R.length;
const VP = new Int16Array(N), VN = new Int16Array(N), VM = new Int16Array(N), VV = new Int16Array(N), VF = new Int16Array(N), VT = new Int16Array(N);
const VU = new Array(N), VC = new Array(N);
for (let i = 0; i < N; i++) {
  const r = R[i];
  VP[i] = parseInt(r[0], 36) - 1; VU[i] = r.substr(1, 2); VN[i] = parseInt(r[3], 36) - 1; VM[i] = parseInt(r[4], 36) - 1;
  VV[i] = parseInt(r[5], 36) - 1; VF[i] = parseInt(r[6], 36);
  const cs = []; let nt = 0;
  for (let k = 7; k < r.length; k += 2) { const c = parseInt(r.substr(k, 2), 36) - 1; cs.push(c); if (COMP[c] && COMP[c].tec) nt++; }
  VC[i] = cs; VT[i] = nt;
}

const VAZIO = {plat: -1, reg: '', uf: '', niv: -1, mod: -1, vin: -1, comp: -1};
const TEXTO = {reg: true, uf: true};
const F = Object.assign({}, VAZIO);
const ativo = () => Object.keys(VAZIO).some(d => F[d] !== VAZIO[d]);

const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/'/g, '&#39;');
const pct = (x, d = 1) => isFinite(x) ? (x * 100).toFixed(d).replace('.', ',') + '%' : 'n/d';
const num = x => String(x).replace(/\B(?=(\d{3})+(?!\d))/g, '.');
const dec = x => x.toFixed(1).replace('.', ',');
const larg = x => (isFinite(x) ? Math.max(0, Math.min(1, x)) * 100 : 0).toFixed(1) + '%';
const est = (sel, k) => sel === VAZIO.comp || sel === '' ? '' : (sel === k ? 'on' : 'off');
const maior = a => a.reduce((m, x) => x > m ? x : m, 0);

function passa(i, sem) {
  const s = d => sem.indexOf(d) >= 0;
  if (F.plat >= 0 && VP[i] !== F.plat) return false;
  if (!s('geo')) {
    if (F.reg && REG[VU[i]] !== F.reg) return false;
    if (F.uf && VU[i] !== F.uf) return false;
  }
  if (!s('niv') && F.niv !== -1 && (F.niv === -2 ? !NIV[VN[i]].ent : VN[i] !== F.niv)) return false;
  if (!s('mod') && F.mod >= 0 && VM[i] !== F.mod) return false;
  if (!s('vin') && F.vin >= 0 && VV[i] !== F.vin) return false;
  if (!s('comp') && F.comp >= 0 && VC[i].indexOf(F.comp) < 0) return false;
  return true;
}
function base(...sem) { const b = []; for (let i = 0; i < N; i++) { if (passa(i, sem)) b.push(i); } return b; }
function contaComp(b) { const c = new Array(COMP.length).fill(0); for (const i of b) { for (const k of VC[i]) c[k]++; } return c; }
function conta(b, V, tam) { const c = new Array(tam).fill(0); for (const i of b) c[V[i]]++; return c; }

function calc() {
  const M = {};
  const b = base();
  const iRem = MOD.indexOf('Remoto'), iHib = MOD.indexOf('Híbrido');
  const kp = {n: b.length, ent: 0, exp: 0, grad: 0, dipl: 0, curs: 0, ing: 0, rem: 0, hib: 0};
  for (const i of b) {
    const f = VF[i];
    if (NIV[VN[i]].ent) { kp.ent++; if (f & 16) kp.exp++; }
    if (f & 1) kp.grad++;
    if (f & 2) kp.dipl++;
    if (f & 4) kp.curs++;
    if (f & 8) kp.ing++;
    if (VM[i] === iRem) kp.rem++;
    if (VM[i] === iHib) kp.hib++;
  }
  M.kp = kp;
  const selTec = F.comp >= 0 && COMP[F.comp].tec, selCom = F.comp >= 0 && !COMP[F.comp].tec;
  const bT = selCom ? b : base('comp'); M.bT = bT.length; M.ccT = contaComp(bT); M.semT = bT.filter(i => VT[i] === 0).length;
  const bC = selTec ? b : base('comp'); M.bC = bC.length; M.ccC = contaComp(bC); M.semC = bC.filter(i => VC[i].length === VT[i]).length;
  const bm = selCom ? base('niv') : base('comp', 'niv');
  M.mxc = contaComp(bm);
  M.mx = GRUPO_IX.map(ix => {
    const g = {n: 0, tec: 0, cnt: new Array(COMP.length).fill(0)};
    for (const i of bm) { if (ix.indexOf(VN[i]) >= 0) { g.n++; g.tec += VT[i]; for (const k of VC[i]) g.cnt[k]++; } }
    return g;
  });
  const bn = base('niv'); M.bn = bn.length; M.niv = conta(bn, VN, NIV.length);
  const bo = base('mod'); M.bo = bo.length; M.mod = conta(bo, VM, MOD.length);
  const bv = base('vin'); M.bv = bv.length; M.vin = conta(bv, VV, VIN.length);
  const bg = base('geo'); M.bg = bg.length; M.uf = {}; M.reg = {};
  for (const i of bg) { const u = VU[i], r = REG[u]; M.uf[u] = (M.uf[u] || 0) + 1; M.reg[r] = (M.reg[r] || 0) + 1; }
  return M;
}

function topo(cont, tec, qtd) {
  const lista = [];
  cont.forEach((v, k) => { if (COMP[k] && COMP[k].tec === tec && v > 0) lista.push({k: k, v: v}); });
  lista.sort((a, b) => b.v - a.v || COMP[a.k].nome.localeCompare(COMP[b.k].nome, 'pt-BR'));
  let top = lista.slice(0, qtd);
  if (F.comp >= 0 && COMP[F.comp].tec === tec && !top.some(x => x.k === F.comp)) {
    const pos = lista.findIndex(x => x.k === F.comp);
    top = top.slice(0, qtd - 1).concat([{k: F.comp, v: pos >= 0 ? lista[pos].v : 0, pos: pos >= 0 ? pos + 1 : 0}]);
  }
  return top;
}

function linha(cls, dim, chave, rot, valor, w, titulo, estado) {
  return `<div class='br ${cls} ${estado}' data-d='${dim}' data-k='${esc(chave)}' title='${esc(titulo)}'><span class='bl'>${esc(rot)}</span><span class='bt'><i style='width:${w}'></i></span><span class='bv'>${valor}</span></div>`;
}
const bloco = (tit, sub, corpo) => `<div class='tl'><div class='tt'>${tit}</div><div class='ts'>${sub}</div>${corpo}</div>`;

const OPC = {
  plat: [[-1, 'Todas']].concat(PLAT.map((x, k) => [k, x])),
  reg: [['', 'Todas']].concat(ORDEM_REGIAO.filter(r => Object.keys(REG).some(u => REG[u] === r)).map(r => [r, r])),
  uf: [['', 'Todas']].concat(Object.keys(REG).filter(u => u !== '--').sort().map(u => [u, u])),
  niv: [[-1, 'Todos'], [-2, 'Vagas de entrada']].concat(NIV.map((x, k) => [k, x.nome])),
  mod: [[-1, 'Todos']].concat(MOD.map((x, k) => [k, x])),
  vin: (() => {
    const c = conta(Array.from({length: N}, (_, i) => i), VV, VIN.length);
    const ks = VIN.map((x, k) => k).filter(k => VIN[k]);
    ks.sort((a, b) => (VIN[b].inf - VIN[a].inf) || (c[b] - c[a]) || VIN[a].nome.localeCompare(VIN[b].nome, 'pt-BR'));
    return [[-1, 'Todas']].concat(ks.map(k => [k, VIN[k].nome]));
  })()
};
const ORD_COMP = COMP.map((x, k) => k).filter(k => COMP[k]).sort((a, b) => COMP[a].nome.localeCompare(COMP[b].nome, 'pt-BR'));

function cabecalho() {
  const sel = (dim, rot) => `<label class='fc${F[dim] !== VAZIO[dim] ? ' at' : ''}'><span>${rot}</span><select data-s='${dim}'>`
    + OPC[dim].map(o => `<option value='${esc(o[0])}'${o[0] === F[dim] ? ' selected' : ''}>${esc(o[1])}</option>`).join('') + `</select></label>`;
  const grupo = (rot, tec) => `<optgroup label='${rot}'>` + ORD_COMP.filter(k => COMP[k].tec === tec)
    .map(k => `<option value='${k}'${k === F.comp ? ' selected' : ''}>${esc(COMP[k].nome)}</option>`).join('') + `</optgroup>`;
  const selComp = `<label class='fc${F.comp >= 0 ? ' at' : ''}'><span>Competência</span><select data-s='comp'><option value='-1'>Todas</option>`
    + grupo('Técnicas', true) + grupo('Comportamentais', false) + `</select></label>`;
  return `<div class='hd'><div class='hd-t'><span class='hd-h'>Empregabilidade em TI</span><span class='hd-s'>Gupy, Sólides e InfoJobs · coleta 27 e 28/09/2026</span></div><div class='fl'>`
    + sel('plat', 'Plataforma') + sel('reg', 'Região') + sel('uf', 'UF') + sel('niv', 'Nível') + sel('mod', 'Modelo') + sel('vin', 'Contratação') + selComp
    + `<button type='button' class='lp' data-limpar='1'${ativo() ? '' : ' disabled'}>Limpar</button></div></div>`;
}

function kpis(M) {
  const k = M.kp, n = k.n;
  const card = (rot, val, nota, barra) => `<div class='kc'><span class='kl'>${rot}</span><b>${val}</b><small>${nota}</small>`
    + (barra === null ? '' : `<div class='kb'><i style='width:${larg(barra)}'></i></div>`) + `</div>`;
  return `<div class='kp'>` + card('Vagas de TI', num(n), 'sem repetição entre plataformas', null)
    + card('Vagas de entrada', pct(k.ent / n), 'aprendiz, estágio, trainee e júnior', k.ent / n)
    + card('Entrada que menciona experiência', k.ent ? pct(k.exp / k.ent) : 'n/d', k.ent ? 'das vagas de entrada' : 'sem vagas de entrada no filtro', k.ent ? k.exp / k.ent : 0)
    + card('Mencionam graduação', pct(k.grad / n), `concluída ${pct(k.dipl / n)} · cursando ${pct(k.curs / n)}`, k.grad / n)
    + card('Citam inglês', pct(k.ing / n), 'como obrigatório ou desejável', k.ing / n)
    + card('Trabalho remoto', pct(k.rem / n), `híbrido: ${pct(k.hib / n)}`, k.rem / n) + `</div>`;
}

function listaComp(tit, tec, M) {
  const cont = tec ? M.ccT : M.ccC, n = tec ? M.bT : M.bC;
  const mesmo = F.comp >= 0 && COMP[F.comp].tec === tec;
  const top = topo(cont, tec, 10);
  const sub = '% das vagas que citam a competência · 10 mais citadas';
  if (!top.length) return bloco(tit, sub, `<div class='vz'>Nenhuma competência no filtro.</div>`);
  const max = maior(top.map(x => x.v));
  const sem = tec ? M.semT : M.semC;
  return bloco(tit, sub, top.map(x => linha('', 'comp', x.k, COMP[x.k].nome + (x.pos ? ` (${x.pos}ª)` : ''), pct(x.v / n), larg(x.v / max),
    `${COMP[x.k].nome}: ${num(x.v)} de ${num(n)} vagas`, mesmo ? est(F.comp, x.k) : '')).join('')
    + `<div class='nt'>Uma vaga pode citar várias. ${num(sem)} das ${num(n)} vagas (${pct(sem / n)}) não citam nenhuma ${tec ? 'técnica' : 'comportamental'} do dicionário.</div>`);
}

function matriz(M) {
  const top = topo(M.mxc, true, 10), G = M.mx, mesmo = F.comp >= 0 && COMP[F.comp].tec;
  const tit = 'Competências técnicas por nível de senioridade';
  const sub = '% das vagas de cada nível que citam a competência · Estágio/Trainee inclui aprendiz';
  if (!top.length) return bloco(tit, sub, `<div class='vz'>Nenhuma competência técnica no filtro.</div>`);
  let max = 0;
  const cel = top.map(x => G.map(g => { const p = g.n ? g.cnt[x.k] / g.n : NaN; if (p > max) max = p; return p; }));
  const nivOn = gi => F.niv === -1 ? '' : (GRUPO_IX[gi].some(ix => F.niv === -2 ? (NIV[ix] && NIV[ix].ent) : ix === F.niv) ? 'on' : '');
  let h = `<table><tr><th></th>` + GRUPOS.map((g, gi) => `<th class='${nivOn(gi)}'>${g[1]}<small>${num(G[gi].n)} vagas</small></th>`).join('') + `</tr>`;
  top.forEach((x, r) => {
    const nome = COMP[x.k].nome;
    h += `<tr><td class='mc ${mesmo ? est(F.comp, x.k) : ''}' data-d='comp' data-k='${x.k}' title='${esc(nome)}'>${esc(nome)}</td>` + cel[r].map((p, gi) => {
      if (!G[gi].n) return `<td class='nd'>n/d</td>`;
      const a = 0.06 + 0.79 * (max ? p / max : 0);
      return `<td style='background:rgba(%%RGB%%,${a.toFixed(2)});color:${a > 0.65 ? '#fff' : '#1B2A3A'}' title='${esc(nome)} · ${GRUPOS[gi][1]}: ${num(G[gi].cnt[x.k])} de ${num(G[gi].n)} vagas'>${pct(p)}</td>`;
    }).join('') + `</tr>`;
  });
  h += `<tr><td class='mr'>Técnicas por vaga</td>` + G.map(g => `<td class='mm'>${g.n ? dec(g.tec / g.n) : 'n/d'}</td>`).join('') + `</tr></table>`;
  return bloco(tit, sub, h);
}

function niveis(M) {
  const max = maior(M.niv);
  const on = k => F.niv === -1 ? '' : ((F.niv === -2 ? NIV[k].ent : F.niv === k) ? 'on' : 'off');
  return bloco('Nível de senioridade', '% das vagas', NIV.map((x, k) => M.niv[k] > 0
    ? linha('b2', 'niv', k, x.nome, pct(M.niv[k] / M.bn), larg(M.niv[k] / max), `${x.nome}: ${num(M.niv[k])} vagas`, on(k)) : '').join(''));
}

function modelos(M) {
  const n = M.bo; let ac = 0; const seg = [], leg = [];
  MOD.forEach((nome, k) => {
    const v = M.mod[k];
    if (!v) return;
    const cor = COR_MODELO[nome] || '#D3DAE2';
    const ini = ac / n * 100; ac += v;
    seg.push(`${F.mod >= 0 && F.mod !== k ? '#DDE3EA' : cor} ${ini.toFixed(2)}% ${(ac / n * 100).toFixed(2)}%`);
    leg.push(`<div class='lg ${est(F.mod, k)}' data-d='mod' data-k='${k}' title='${esc(nome)}: ${num(v)} vagas'><i style='background:${cor}'></i><span>${esc(nome)}</span><b>${pct(v / n)}</b></div>`);
  });
  const kc = F.mod >= 0 ? F.mod : M.mod.indexOf(maior(M.mod));
  const centro = n && kc >= 0 ? `<b>${(M.mod[kc] / n * 100).toFixed(0)}%</b><span>${esc(MOD[kc].toLowerCase())}</span>` : '';
  return bloco('Modelo de trabalho', '% das vagas', `<div class='dw'><div class='dn' style='background:conic-gradient(${seg.join(',') || '#EDF0F4 0% 100%'})'><div class='dh'>${centro}</div></div><div class='dl'>${leg.join('')}</div></div>`);
}

function vinculos(M) {
  let inf = 0;
  M.vin.forEach((v, k) => { if (VIN[k] && VIN[k].inf) inf += v; });
  const nao = M.bv - inf;
  const lista = [];
  M.vin.forEach((v, k) => { if (VIN[k] && VIN[k].inf && v > 0) lista.push({k: k, v: v}); });
  lista.sort((a, b) => b.v - a.v || VIN[a.k].nome.localeCompare(VIN[b.k].nome, 'pt-BR'));
  let top = lista.slice(0, 5);
  if (F.vin >= 0 && VIN[F.vin].inf && !top.some(x => x.k === F.vin)) top = top.slice(0, 4).concat([lista.find(x => x.k === F.vin) || {k: F.vin, v: 0}]);
  // formas menos frequentes agrupadas em "Outras"
  const resto = lista.filter(x => !top.some(t => t.k === x.k)), vResto = resto.reduce((s, x) => s + x.v, 0);
  const max = maior(top.map(x => x.v).concat([vResto]));
  const outras = vResto ? `<div class='br b3 ${est(F.vin, -9)}' title='${esc(resto.map(x => `${VIN[x.k].nome}: ${num(x.v)}`).join(' · '))}'>`
    + `<span class='bl'>Outras (${resto.length})</span><span class='bt'><i style='width:${larg(vResto / max)}'></i></span><span class='bv'>${pct(vResto / inf)}</span></div>` : '';
  const corpo = top.length ? top.map(x => linha('b3', 'vin', x.k, VIN[x.k].nome, pct(x.v / inf), larg(x.v / max), `${VIN[x.k].nome}: ${num(x.v)} vagas`, est(F.vin, x.k))).join('') + outras
    : `<div class='vz'>Nenhuma vaga com contratação informada no filtro.</div>`;
  const kNao = VIN.findIndex(x => x && !x.inf);
  const nota = `<div class='nt ${kNao >= 0 && F.vin === kNao ? 'on' : ''}'${kNao >= 0 ? ` data-d='vin' data-k='${kNao}'` : ''} title='Clique para filtrar as vagas sem informação de contratação'>Sem informação: ${num(nao)} vagas (a InfoJobs informa só a jornada).</div>`;
  return bloco('Forma de contratação', `% das ${num(inf)} vagas com contratação informada`, corpo + nota);
}

function local(M) {
  const v = MAPA.map(m => M.uf[m[0]] || 0), max = maior(v);
  const quadros = MAPA.map((m, j) => {
    const uf = m[0], a = v[j] > 0 ? 0.12 + 0.78 * Math.sqrt(v[j] / max) : 0;
    const fora = (F.reg && REG[uf] !== F.reg) || (F.uf && F.uf !== uf);
    const fundo = v[j] > 0 ? `rgba(%%RGB%%,${a.toFixed(2)})` : '#EDF0F4';
    return `<div class='${fora ? 'off' : ''}${F.uf === uf ? ' on' : ''}' data-d='uf' data-k='${uf}' title='${uf}: ${num(v[j])} vagas' style='grid-row:${m[1]};grid-column:${m[2]};background:${fundo};color:${a > 0.55 ? '#fff' : '#33414F'}'>${uf}</div>`;
  }).join('');
  const regs = Object.keys(M.reg).map(r => ({r: r, v: M.reg[r]})).sort((a, b) => b.v - a.v || a.r.localeCompare(b.r, 'pt-BR'));
  const maxR = maior(regs.map(x => x.v));
  const sel = F.reg || (F.uf ? REG[F.uf] : '');
  const linhas = regs.map(x => linha('b4', 'reg', x.r, x.r, pct(x.v / M.bg), larg(x.v / maxR), `${x.r}: ${num(x.v)} vagas`, sel ? (sel === x.r ? 'on' : 'off') : '')).join('');
  const semUf = M.uf['--'] || 0;
  const nota = semUf ? `<div class='nt'>Fora do mapa: ${num(semUf)} vagas sem estado (remotas ou sem cidade no anúncio).</div>` : '';
  return bloco('Localização das vagas', 'Mapa por estado (mais escuro, mais vagas) · % por região', `<div class='mw'><div class='mp'>${quadros}</div><div class='mr'>${linhas}${nota}</div></div>`);
}

function render() {
  const M = calc();
  let h = cabecalho();
  if (!M.kp.n) {
    h += `<div class='tl'><div class='tt'>Nenhuma vaga para os filtros selecionados</div><div class='ts'>Altere ou limpe os filtros.</div></div>`;
  } else {
    h += kpis(M) + `<div class='r2'>` + listaComp('Competências técnicas mais citadas', true, M) + matriz(M) + listaComp('Competências comportamentais mais citadas', false, M) + `</div>`
      + `<div class='r3'>` + niveis(M) + modelos(M) + vinculos(M) + local(M) + `</div>`
      + `<div class='ft'><span>Vagas de TI identificadas pelo título (e pelas tecnologias da descrição nos títulos ambíguos), sem repetição entre plataformas · competências por dicionário de 82 termos, contadas uma vez por vaga · a menção não distingue o obrigatório do desejável</span><span>Clique nas barras, no mapa ou na legenda para filtrar</span></div>`;
  }
  root.innerHTML = h;
}

root.addEventListener('change', e => {
  const s = e.target.closest('select[data-s]');
  if (!s) return;
  const d = s.getAttribute('data-s');
  F[d] = TEXTO[d] ? s.value : parseInt(s.value, 10);
  if (d === 'reg' && F.reg) F.uf = '';
  if (d === 'uf' && F.uf) F.reg = '';
  render();
});
root.addEventListener('click', e => {
  if (e.target.closest('[data-limpar]')) { Object.assign(F, VAZIO); render(); return; }
  const el = e.target.closest('[data-d]');
  if (!el) return;
  const d = el.getAttribute('data-d'), k = el.getAttribute('data-k');
  const v = TEXTO[d] ? k : parseInt(k, 10);
  F[d] = F[d] === v ? VAZIO[d] : v;
  if (d === 'reg' && F.reg) F.uf = '';
  if (d === 'uf' && F.uf) F.reg = '';
  render();
});
root.__calc = filtros => { const salvo = Object.assign({}, F); Object.assign(F, VAZIO, filtros); const M = calc(); Object.assign(F, salvo); return M; };
root.__filtrar = filtros => { Object.assign(F, VAZIO, filtros); render(); };
render();
