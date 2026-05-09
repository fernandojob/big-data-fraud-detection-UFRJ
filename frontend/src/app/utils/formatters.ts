export function formatarMoeda(valor: number): string {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL'
  }).format(valor);
}

export function formatarStatus(status: string): string {
  return status.replace('_', ' ');
}

export function formatarData(data: string): string {
  return new Date(data).toLocaleString('pt-BR');
}

export function formatarPais(pais: string): string {
  try {
    const regionNames = new Intl.DisplayNames(['pt-BR'], { type: 'region' });
    return regionNames.of(pais) || pais;
  } catch {
    return pais;
  }
}