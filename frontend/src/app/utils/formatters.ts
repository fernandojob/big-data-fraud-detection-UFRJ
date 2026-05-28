export function formatarMoeda(valor: number): string {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL'
  }).format(valor);
}

export function formatarStatus(status: string): string {
  return status.replace('_', ' ');
}

export function formatarMotivo(motivo: string): string {
  const labels: Record<string, string> = {
    IMPOSSIBLE_TRAVEL: 'Viagem impossivel',
    VALUE_ABOVE_USER_PROFILE: 'Valor fora do perfil',
    NEW_DEVICE: 'Dispositivo novo',
    NEW_COUNTRY_FOR_USER: 'Pais novo',
    HIGH_ATTEMPT_COUNT: 'Muitas tentativas',
    UNUSUAL_TRANSACTION_HOUR: 'Horario incomum',
    ABNORMAL_FREQUENCY: 'Frequencia anormal'
  };

  return labels[motivo] || motivo.replaceAll('_', ' ');
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
