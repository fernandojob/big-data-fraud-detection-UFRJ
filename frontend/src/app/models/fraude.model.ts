export interface Fraude {
  id_transacao: string;
  valor: number;
  status: 'ALTA_SUSPEITA' | 'MEDIA_SUSPEITA' | 'NORMAL';
  pais: string;
  device: string;
  data_hora: string;
  tentativas: number;
}