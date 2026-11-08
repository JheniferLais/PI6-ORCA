/**
 * Tokens da sessão da extensão (access + refresh), guardados no IndexedDB da
 * origem da extensão (chrome-extension://<id>).
 *
 * Por que não chrome.storage.local? Content scripts conseguem ler o
 * chrome.storage.local, e eles rodam dentro de páginas quaisquer. O IndexedDB
 * do service worker só é acessível pela própria extensão (popup e SW), e
 * persiste ao fechar o navegador (o chrome.storage.session não persiste).
 */

export interface Credenciais {
  access: string;
  refresh: string;
}

const BANCO = 'orca';
const TABELA = 'credenciais';
const CHAVE = 'sessao';

let conexao: Promise<IDBDatabase> | null = null;

function abrir(): Promise<IDBDatabase> {
  if (!conexao) {
    conexao = new Promise((resolve, reject) => {
      const pedido = indexedDB.open(BANCO, 1);
      pedido.onupgradeneeded = () => pedido.result.createObjectStore(TABELA);
      pedido.onsuccess = () => resolve(pedido.result);
      pedido.onerror = () => {
        conexao = null;
        reject(pedido.error);
      };
    });
  }
  return conexao;
}

async function executar<T>(modo: IDBTransactionMode, fazer: (t: IDBObjectStore) => IDBRequest): Promise<T> {
  const banco = await abrir();
  return new Promise<T>((resolve, reject) => {
    const pedido = fazer(banco.transaction(TABELA, modo).objectStore(TABELA));
    pedido.onsuccess = () => resolve(pedido.result as T);
    pedido.onerror = () => reject(pedido.error);
  });
}

export async function lerCredenciais(): Promise<Credenciais | null> {
  const valor = await executar<Credenciais | undefined>('readonly', (t) => t.get(CHAVE));
  return valor?.access && valor.refresh ? valor : null;
}

export async function salvarCredenciais(c: Credenciais): Promise<void> {
  await executar('readwrite', (t) => t.put(c, CHAVE));
}

export async function apagarCredenciais(): Promise<void> {
  await executar('readwrite', (t) => t.delete(CHAVE));
}
