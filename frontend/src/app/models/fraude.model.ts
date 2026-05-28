export interface Fraude {
  id_transacao: string;
  id_usuario: string;
  valor: number;
  risk_score: number;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  risk_reasons: string[];
  decision: 'APPROVE' | 'REVIEW' | 'BLOCK';
  pais_residencia: string;
  pais_transacao: string;
  pais_anterior?: string;
  cidade_transacao: string;
  cidade_anterior?: string;
  device: string;
  device_principal: string;
  data_hora: string;
  tentativas: number;
  velocidade_kmh_entre_transacoes?: number;
  distancia_km_desde_ultima_transacao?: number;
  minutos_desde_ultima_transacao?: number;
  valor_acima_do_perfil: boolean;
  device_novo: boolean;
  pais_novo_para_usuario: boolean;
}
