/** Popup do ícone: estado da extensão, liga/desliga o monitoramento e logout. */
import { CONFIG } from '../config';
import { ESTADO_INICIAL, monitoramentoAtivo, type EstadoExtensao, type PopupMessage } from '../models/content';

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

const NIVEL: Record<string, string> = { BLOCK: 'bloqueio', ALERT: 'alerta' };
let ocupado = false;

function aviso(texto: string): void {
  $('aviso').textContent = texto;
}

function render(e: EstadoExtensao): void {
  const conectado = e.sessao === 'ativa' && !!e.usuario;
  $('conectado').hidden = !conectado;
  $('desconectado').hidden = conectado;
  $('sair').hidden = !conectado;
  $('desconectado-titulo').textContent =
    e.sessao === 'expirada' ? 'Sessão expirada' : 'Extensão não conectada';

  if (conectado) {
    const chave = $<HTMLButtonElement>('chave');
    chave.setAttribute('aria-checked', String(e.monitorando));
    chave.disabled = ocupado;
    $('monitor-titulo').textContent = `Monitoramento: ${e.monitorando ? 'ligado' : 'desligado'}`;
    $('monitor-descricao').textContent = monitoramentoAtivo(e)
      ? e.backend === 'indisponivel'
        ? 'Servidor fora do ar: análises pausadas.'
        : 'Analisando as páginas visitadas.'
      : 'Nenhuma página é analisada.';
    $('conta').textContent = e.usuario!.email;

    const [cor, texto] =
      e.backend === 'ok' ? ['verde', 'conectado'] : e.backend === 'indisponivel' ? ['vermelho', 'indisponível'] : ['', 'verificando'];
    $('servidor-ponto').className = `ponto ${cor}`;
    $('servidor').textContent = texto;

    const u = e.ultimaAnalise;
    $('ultima').textContent = u
      ? `${new URL(u.url).hostname}: ${u.nivel ? NIVEL[u.nivel] : 'permitida'}${u.log === 'gravado' ? ' (registrada)' : ''}`
      : '—';
  }

  if (!ocupado) aviso(e.erro ?? '');
}

async function enviar(m: PopupMessage): Promise<{ ok: boolean; erro?: string } | undefined> {
  return chrome.runtime.sendMessage(m);
}

async function estadoAtual(): Promise<EstadoExtensao> {
  const d = await chrome.storage.local.get('estado');
  return { ...ESTADO_INICIAL, ...(d.estado as Partial<EstadoExtensao> | undefined) };
}

$('chave').addEventListener('click', async () => {
  const e = await estadoAtual();
  ocupado = true;
  render(e);
  aviso('Salvando...');
  const r = await enviar({ type: 'SET_MONITORING', enabled: !e.monitorando });
  ocupado = false;
  aviso(r?.ok ? '' : r?.erro ?? 'Não foi possível alterar o monitoramento.');
  render(await estadoAtual());
});

$('sair').addEventListener('click', async () => {
  ocupado = true;
  aviso('Saindo...');
  await enviar({ type: 'LOGOUT' });
  ocupado = false;
  render(await estadoAtual());
});

$('abrir').addEventListener('click', () => {
  void chrome.tabs.create({ url: CONFIG.dashboardUrl });
  window.close();
});

chrome.storage.onChanged.addListener((mudancas, area) => {
  if (area === 'local' && mudancas.estado) void estadoAtual().then(render);
});

void estadoAtual().then(render);
void enviar({ type: 'SYNC' }); // confere o backend ao abrir
