export type StatusCode =
  | "GRIS_INFORMATIVO"
  | "AZUL_ATENDIDO"
  | "ROJO_VENCIDO"
  | "AMBAR_POR_VENCER"
  | "VERDE_EN_TIEMPO";
export type Semaphore = {
  codigo: StatusCode;
  etiqueta: string;
  dias_habiles: number | null;
};
export type User = {
  username: string;
  role:
    | "Administrador"
    | "Oficialia_Despachador"
    | "Responsable_Area"
    | "Auditor";
  area: string;
  display_name: string;
};
export type Person = {
  id: number;
  nombre_normalizado: string;
  nombre_mostrar: string;
  cargo: string;
  dependencia_unidad: string;
  prefijo_oficio_frecuente: string;
  es_interno: boolean;
  activo: boolean;
  version: number;
};
export type Area = {
  clave: string;
  nombre: string;
  titular_nombre: string;
  analistas_sugeridos_json: string[];
};
export type Config = {
  today: string;
  timezone: string;
  business_calendar: string;
  areas: Area[];
};
export type Oficio = {
  id: number;
  anio: number;
  folio_ssg: string;
  consecutivo_anual: number;
  numero_oficio: string;
  fecha_oficio: string;
  fecha_recepcion: string;
  naturaleza: "ORIGINAL" | "CC";
  requiere_respuesta: boolean;
  plazo_tipo: string;
  plazo_dias_habiles: number | null;
  fecha_limite_respuesta: string | null;
  dirigido_nombre: string;
  dirigido_cargo: string;
  firmante_nombre: string;
  firmante_cargo: string;
  copias_dirigido_json: { nombre: string; cargo: string }[];
  asunto: string;
  area_asignada: string;
  responsables_detalle: string;
  observaciones_fisicas: string;
  tiene_documento_entrada: boolean;
  documento_entrada_nombre: string | null;
  documento_entrada_disponible: boolean;
  estatus_atencion: string;
  nota_atencion: string | null;
  oficio_respuesta_numero: string | null;
  fecha_atencion: string | null;
  tiene_acuse_respuesta: boolean;
  acuse_respuesta_nombre: string | null;
  acuse_respuesta_disponible: boolean;
  version: number;
  created_at: string;
  updated_at: string;
  semaforo: Semaphore;
};
export type Summary = {
  total: number;
  vencidos: number;
  por_vencer: number;
  en_tiempo: number;
  atendidos: number;
  informativos: number;
  fecha_referencia: string;
  gerencias: {
    area: string;
    total: number;
    atendidos: number;
    cumplimiento: number;
  }[];
};
export type Audit = {
  id: number;
  actor_username: string;
  action: string;
  entity_type: string;
  entity_id: string;
  created_at: string;
  before_json: Record<string, unknown> | null;
  after_json: Record<string, unknown> | null;
};
