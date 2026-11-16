import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
import {
  api,
  clearSession,
  download,
  errorMessage,
  hasSession,
  login,
} from "./api";
import type { Audit, Config, Oficio, Person, Summary, User } from "./types";
import logo from "./assets/sello-ssg.png";
import { Icon } from "./components/Icon";
import { Badge } from "./components/Badge";
import { Modal } from "./components/Modal";
import { OficioForm } from "./components/OficioForm";
import { AttentionForm } from "./components/AttentionForm";

const dateLabel = (value: string | null) =>
  value ? value.slice(0, 10).split("-").reverse().join("/") : "Por definir";
const canDispatch = (user: User) =>
  ["Administrador", "Oficialia_Despachador"].includes(user.role);

function LoginScreen({ onLogin }: { onLogin: (user: User) => void }) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const data = new FormData(event.currentTarget);
    try {
      onLogin(
        await login(String(data.get("username")), String(data.get("password"))),
      );
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="login-page">
      <section className="login-intro">
        <div className="brand">
          <img src={logo} alt="Emblema SSG" />
          <div>
            <strong>
              SICOA<span>—SSG</span>
            </strong>
            <small>SERVICIOS GENERALES</small>
          </div>
        </div>
        <div className="login-message">
          <div className="login-title">
            Control de oficios,
            <br />
            <em>turnos y alertas</em>
          </div>
          <div className="login-flow">
            <span>
              <Icon name="inbox" />
              Recepción
            </span>
            <i />
            <span>
              <Icon name="clock" />
              Seguimiento
            </span>
            <i />
            <span>
              <Icon name="check" />
              Atención
            </span>
          </div>
        </div>
        <p className="login-footer">
          SUBDIRECCIÓN DE SERVICIOS GENERALES{" "}
          <span className="mono">/ 2026</span>
        </p>
      </section>
      <section className="login-form-panel">
        <form onSubmit={submit}>
          <span className="login-symbol">
            <Icon name="shield" size={28} />
          </span>
          <span className="eyebrow">ACCESO AL SISTEMA</span>
          <h1>Bienvenido a SICOA-SSG</h1>
          <p className="muted">Ingresa con tu cuenta de operación.</p>
          {error && (
            <div className="error-box" role="alert">
              {error}
            </div>
          )}
          <label>
            Usuario
            <input
              name="username"
              autoComplete="username"
              autoFocus
              required
              placeholder="Tu usuario"
            />
          </label>
          <label>
            Contraseña
            <input
              name="password"
              type="password"
              autoComplete="current-password"
              required
              placeholder="Tu contraseña"
            />
          </label>
          <button className="button primary" disabled={busy}>
            {busy ? "Validando acceso…" : "Iniciar sesión"}
            <Icon name="arrow" />
          </button>
          <p className="login-note">
            El acceso y las operaciones se limitan al rol de tu cuenta.
          </p>
        </form>
      </section>
    </main>
  );
}

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(hasSession());
  useEffect(() => {
    const expired = () => {
      setUser(null);
      setChecking(false);
    };
    window.addEventListener("sicoa-session-expired", expired);
    if (hasSession())
      api<User>("/auth/me")
        .then(setUser)
        .catch(() => clearSession())
        .finally(() => setChecking(false));
    return () => window.removeEventListener("sicoa-session-expired", expired);
  }, []);
  if (checking)
    return (
      <main className="loading-screen" role="status">
        Verificando sesión…
      </main>
    );
  return user ? (
    <Console
      user={user}
      onLogout={() => {
        clearSession();
        setUser(null);
      }}
    />
  ) : (
    <LoginScreen onLogin={setUser} />
  );
}

function Console({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [config, setConfig] = useState<Config | null>(null);
  const [people, setPeople] = useState<Person[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [items, setItems] = useState<Oficio[]>([]);
  const [selected, setSelected] = useState<Oficio | null>(null);
  const [marked, setMarked] = useState<number[]>([]);
  const [query, setQuery] = useState("");
  const [area, setArea] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [revision, setRevision] = useState(0);
  const [capture, setCapture] = useState<{
    next: string;
    record?: Oficio;
  } | null>(null);
  const [attention, setAttention] = useState(false);
  const [directory, setDirectory] = useState(false);
  const [audit, setAudit] = useState<Audit[] | null>(null);
  const [mobileInspector, setMobileInspector] = useState(false);
  const [reports, setReports] = useState(false);
  const [mobileMenu, setMobileMenu] = useState(false);
  const importRef = useRef<HTMLInputElement>(null);
  const documentRef = useRef<HTMLInputElement>(null);
  const reload = useCallback(() => setRevision((value) => value + 1), []);
  const refreshPeople = useCallback(
    () => api<Person[]>("/funcionarios").then(setPeople),
    [],
  );
  useEffect(() => {
    api<Config>("/config")
      .then(setConfig)
      .catch((e) => setError(errorMessage(e)));
    refreshPeople().catch((e) => setError(errorMessage(e)));
  }, [refreshPeople]);
  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(
      () => {
        setLoading(true);
        const params = new URLSearchParams({
          q: query,
          area,
          semaforo: status,
          page: String(page),
          page_size: "50",
        });
        Promise.all([
          api<{ items: Oficio[]; total: number }>(`/oficios?${params}`, {
            signal: controller.signal,
          }),
          api<Summary>("/reportes/resumen", { signal: controller.signal }),
        ])
          .then(([list, metrics]) => {
            setItems(list.items);
            setTotal(list.total);
            setSummary(metrics);
            setSelected(
              (current) =>
                list.items.find((r) => r.id === current?.id) ||
                list.items[0] ||
                null,
            );
          })
          .catch((e) => {
            if (!controller.signal.aborted) setError(errorMessage(e));
          })
          .finally(() => {
            if (!controller.signal.aborted) setLoading(false);
          });
      },
      query ? 180 : 0,
    );
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, area, status, page, revision]);
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(""), 7000);
    return () => clearTimeout(timer);
  }, [notice]);
  async function run(action: () => Promise<unknown>) {
    setError("");
    try {
      await action();
    } catch (err) {
      setError(errorMessage(err));
    }
  }
  async function newRecord() {
    await run(async () => {
      const next = await api<{ folio_ssg: string; disponible: boolean }>(
        "/oficios/next-folio",
      );
      if (!next.disponible) throw new Error("Se agotó el rango de folios.");
      setCapture({ next: next.folio_ssg });
    });
  }
  function saved(record: Oficio) {
    setSelected(record);
    setCapture(null);
    setAttention(false);
    setNotice(
      `${record.folio_ssg}: cambios guardados. Versión ${record.version}.`,
    );
    reload();
  }
  function filter(value: string) {
    setStatus(value);
    setPage(1);
  }
  async function importFile(file?: File) {
    if (!file) return;
    await run(async () => {
      const form = new FormData();
      form.append("file", file);
      const result = await api<{
        importados: number;
        correcciones: string[];
        ya_importado: boolean;
        duplicados_conservados: string[];
      }>("/oficios/import-excel", { method: "POST", body: form });
      setNotice(
        result.ya_importado
          ? "Este archivo ya se había importado. Se conservaron los datos."
          : `${result.importados} oficios importados; ${result.correcciones.length} correcciones de columnas; ${result.duplicados_conservados.length} folios existentes conservados.`,
      );
      reload();
      await refreshPeople();
    });
  }
  async function uploadEntry(file?: File) {
    if (!file || !selected) return;
    await run(async () => {
      const form = new FormData();
      form.append("version", String(selected.version));
      form.append("file", file);
      saved(
        await api<Oficio>(`/oficios/${selected.id}/documento`, {
          method: "POST",
          body: form,
        }),
      );
    });
  }
  const selectRecord = (record: Oficio) => {
    setSelected(record);
    setMobileInspector(true);
  };
  const toggleMarked = (id: number) => {
    setMarked((previous) => {
      if (previous.includes(id))
        return previous.filter((value) => value !== id);
      if (previous.length >= 10) {
        setNotice("Cada hoja de entrega admite hasta 10 oficios.");
        return previous;
      }
      return [...previous, id];
    });
  };
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <img src={logo} alt="Emblema SSG" />
          <div>
            <strong>
              SICOA<span>—SSG</span>
            </strong>
            <small>CONTROL INSTITUCIONAL</small>
          </div>
        </div>
        <div className="sidebar-section">OPERACIÓN</div>
        <nav aria-label="Navegación principal">
          <button
            className="nav-item active"
            onClick={() => {
              setQuery("");
              setArea("");
              filter("");
            }}
          >
            <Icon name="inbox" />
            Correspondencia
            <span className="nav-marker" />
          </button>
          <button className="nav-item" onClick={() => setDirectory(true)}>
            <Icon name="users" />
            Directorio
          </button>
          <button className="nav-item" onClick={() => setReports(true)}>
            <Icon name="file" />
            Reportes y entrega
          </button>
          {["Administrador", "Auditor"].includes(user.role) && (
            <button
              className="nav-item"
              onClick={() =>
                run(async () => setAudit(await api<Audit[]>("/audit-logs")))
              }
            >
              <Icon name="history" />
              Bitácora
            </button>
          )}
        </nav>
        <div className="sidebar-bottom">
          <div className="office-mark">
            <span>SSG</span>
            <p>
              Subdirección de
              <br />
              Servicios Generales
            </p>
          </div>
          <div className="sidebar-year">
            <span>EJERCICIO</span>
            <b className="mono">2026</b>
          </div>
          <div className="sidebar-rule" />
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <button
            className="icon-button mobile-menu-button"
            aria-label="Abrir menú de operación"
            onClick={() => setMobileMenu(true)}
          >
            <Icon name="inbox" />
          </button>
          <div className="breadcrumb">
            <span>Oficialía de partes</span>
            <span>/</span>
            <strong>Correspondencia</strong>
          </div>
          <div className="session-tools">
            <span className="online-state">
              <i />
              Sesión activa
            </span>
            <div className="avatar" aria-hidden="true">
              {user.username.slice(0, 2).toUpperCase()}
            </div>
            <div className="user-info">
              <strong>{user.username}</strong>
              <small>{user.role.replaceAll("_", " ")}</small>
            </div>
            <button
              className="icon-button"
              onClick={onLogout}
              aria-label="Cerrar sesión"
            >
              <Icon name="exit" />
            </button>
          </div>
        </header>
        <main className="workspace">
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                MESA DE CONTROL <span className="mono">/ SSG</span>
              </div>
              <h1>Control de correspondencia</h1>
              <p>Recibe, turna y da seguimiento a cada oficio.</p>
            </div>
            {canDispatch(user) && (
              <button
                className="button primary"
                onClick={newRecord}
                disabled={!config}
              >
                <Icon name="plus" />
                Nuevo oficio
              </button>
            )}
          </div>
          {error && (
            <div className="error-banner" role="alert">
              <span>{error}</span>
              <button
                className="text-button"
                onClick={() => {
                  setError("");
                  reload();
                }}
              >
                Recargar
              </button>
              <button
                className="icon-button"
                onClick={() => setError("")}
                aria-label="Cerrar aviso"
              >
                <Icon name="close" />
              </button>
            </div>
          )}
          <div className="kpi-grid" aria-label="Resumen de correspondencia">
            {[
              {
                label: "Oficios registrados",
                value: summary?.total,
                icon: "inbox",
                style: "",
                detail: `${summary?.informativos ?? 0} informativos`,
              },
              {
                label: "Vencidos",
                value: summary?.vencidos,
                icon: "alert",
                style: "red",
                detail: "Requieren atención inmediata",
              },
              {
                label: "Por vencer / sin plazo",
                value: summary?.por_vencer,
                icon: "clock",
                style: "amber",
                detail: "Hasta 2 días hábiles o sin fecha",
              },
              {
                label: "Atendidos",
                value: summary?.atendidos,
                icon: "check",
                style: "blue",
                detail: "Gestión registrada",
              },
            ].map((metric) => (
              <div className={`kpi ${metric.style}`} key={metric.label}>
                <div>
                  <span>{metric.label}</span>
                  <Icon name={metric.icon} />
                </div>
                <strong className="mono">{metric.value ?? "—"}</strong>
                <small>{metric.detail}</small>
              </div>
            ))}
          </div>
          <div className="operation-grid">
            <section className="records-panel" aria-labelledby="inbox-title">
              <div className="panel-heading">
                <div>
                  <h2 id="inbox-title">Bandeja de oficios</h2>
                  <span className="count-pill mono">{total}</span>
                </div>
                <div className="panel-actions">
                  {canDispatch(user) && (
                    <>
                      <button
                        className="text-button"
                        onClick={() => importRef.current?.click()}
                      >
                        <Icon name="plus" />
                        Importar
                      </button>
                      <input
                        ref={importRef}
                        className="visually-hidden"
                        type="file"
                        accept=".xlsx"
                        aria-label="Importar archivo Excel"
                        tabIndex={-1}
                        onChange={(e) => {
                          importFile(e.target.files?.[0]);
                          e.target.value = "";
                        }}
                      />
                    </>
                  )}
                  <button
                    className="text-button"
                    onClick={() =>
                      run(() =>
                        download(
                          "/oficios/export-excel",
                          "correspondencia-2026.xlsx",
                        ),
                      )
                    }
                  >
                    <Icon name="download" />
                    <span>Excel</span>
                  </button>
                </div>
              </div>
              <div
                className="filter-tabs"
                role="group"
                aria-label="Filtrar por semáforo"
              >
                {[
                  ["", "Todos"],
                  ["ROJO_VENCIDO", "Vencidos"],
                  ["AMBAR_POR_VENCER", "Por vencer"],
                  ["AZUL_ATENDIDO", "Atendidos"],
                  ["GRIS_INFORMATIVO", "Informativos"],
                ].map(([value, label]) => (
                  <button
                    key={value}
                    aria-pressed={status === value}
                    onClick={() => filter(value)}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <div className="search-row">
                <div className="search-input">
                  <Icon name="search" />
                  <input
                    aria-label="Buscar oficios"
                    placeholder="Buscar folio, número o asunto…"
                    value={query}
                    onChange={(e) => {
                      setQuery(e.target.value);
                      setPage(1);
                    }}
                  />
                </div>
                <select
                  aria-label="Filtrar por área"
                  value={area}
                  onChange={(e) => {
                    setArea(e.target.value);
                    setPage(1);
                  }}
                >
                  <option value="">Todas las áreas</option>
                  {config?.areas.map((item) => (
                    <option key={item.clave}>{item.clave}</option>
                  ))}
                </select>
              </div>
              <div className="table-scroll" aria-busy={loading}>
                <table className="records-table">
                  <caption className="visually-hidden">
                    Correspondencia institucional
                  </caption>
                  <thead>
                    <tr>
                      <th className="check-col">
                        <span className="visually-hidden">Entrega</span>
                      </th>
                      <th>FOLIO / OFICIO</th>
                      <th>ASUNTO</th>
                      <th>ÁREA</th>
                      <th>RECEPCIÓN</th>
                      <th>SEMÁFORO</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((record) => (
                      <tr
                        key={record.id}
                        className={selected?.id === record.id ? "selected" : ""}
                      >
                        <td className="check-col">
                          <input
                            type="checkbox"
                            aria-label={`Marcar ${record.folio_ssg} para entrega`}
                            checked={marked.includes(record.id)}
                            onChange={() => toggleMarked(record.id)}
                          />
                        </td>
                        <td>
                          <button
                            className="folio-link mono"
                            onClick={() => selectRecord(record)}
                          >
                            {record.folio_ssg}
                          </button>
                          <span
                            className="office-number mono"
                            title={record.numero_oficio}
                          >
                            {record.numero_oficio}
                          </span>
                        </td>
                        <td className="subject-cell">
                          <button onClick={() => selectRecord(record)}>
                            {record.asunto}
                          </button>
                          <small>{record.firmante_nombre}</small>
                        </td>
                        <td>
                          <span className="area-tag mono">
                            {record.area_asignada}
                          </span>
                        </td>
                        <td className="mono date-cell">
                          {dateLabel(record.fecha_recepcion)}
                        </td>
                        <td>
                          <Badge value={record.semaforo} />
                          {record.semaforo.dias_habiles !== null && (
                            <small className="day-count mono">
                              {record.semaforo.dias_habiles < 0
                                ? `${Math.abs(record.semaforo.dias_habiles)} d de atraso`
                                : `${record.semaforo.dias_habiles} d hábiles`}
                            </small>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!items.length && (
                  <div className="empty-state">
                    <Icon name="inbox" size={32} />
                    <h3>
                      {loading
                        ? "Cargando correspondencia…"
                        : "No hay oficios en esta vista"}
                    </h3>
                    <p>
                      {loading
                        ? "Consultando el registro institucional."
                        : "Ajusta la búsqueda o registra un nuevo oficio."}
                    </p>
                  </div>
                )}
              </div>
              <footer className="table-footer">
                <span className="mono">
                  {total ? (page - 1) * 50 + 1 : 0}–{Math.min(page * 50, total)}{" "}
                  de {total}
                </span>
                {marked.length > 0 && (
                  <button
                    className="text-button"
                    onClick={() => setReports(true)}
                  >
                    Entrega <span className="mono">({marked.length})</span>
                  </button>
                )}
                <div>
                  <button
                    className="icon-button"
                    disabled={page === 1 || loading}
                    onClick={() => setPage((p) => p - 1)}
                    aria-label="Página anterior"
                  >
                    <span className="rotate">
                      <Icon name="arrow" />
                    </span>
                  </button>
                  <span className="mono">
                    {page} / {Math.max(1, Math.ceil(total / 50))}
                  </span>
                  <button
                    className="icon-button"
                    disabled={page * 50 >= total || loading}
                    onClick={() => setPage((p) => p + 1)}
                    aria-label="Página siguiente"
                  >
                    <Icon name="arrow" />
                  </button>
                </div>
              </footer>
            </section>
            <aside
              className={`inspector ${mobileInspector ? "mobile-open" : ""}`}
              aria-label="Inspector del oficio"
            >
              <div className="inspector-heading">
                <span className="eyebrow">INSPECTOR DEL OFICIO</span>
                <button
                  className="icon-button mobile-close"
                  aria-label="Cerrar inspector"
                  onClick={() => setMobileInspector(false)}
                >
                  <Icon name="close" />
                </button>
                <Icon name="file" />
              </div>
              {selected ? (
                <>
                  <div className="inspector-body">
                    <div className="inspector-id">
                      <strong className="mono">{selected.folio_ssg}</strong>
                      <span className="version mono">V{selected.version}</span>
                    </div>
                    <p className="inspector-number mono">
                      {selected.numero_oficio}
                    </p>
                    <Badge value={selected.semaforo} />
                    <div className="inspector-section">
                      <span className="field-title">ASUNTO</span>
                      <p className="full-subject">{selected.asunto}</p>
                    </div>
                    <div className="inspector-section">
                      <span className="field-title">ORIGEN</span>
                      <p>
                        {selected.firmante_nombre || "Sin firmante registrado"}
                      </p>
                      <small>{selected.firmante_cargo}</small>
                      <span className="field-title spaced">DIRIGIDO A</span>
                      <p>{selected.dirigido_nombre}</p>
                      <small>{selected.dirigido_cargo}</small>
                      {selected.copias_dirigido_json.map((copy, index) => (
                        <p className="copy-detail" key={index}>
                          CC: {copy.nombre}
                          <small>{copy.cargo}</small>
                        </p>
                      ))}
                    </div>
                    <div className="inspector-section timeline">
                      <div>
                        <span>Recepción</span>
                        <strong className="mono">
                          {dateLabel(selected.fecha_recepcion)}
                        </strong>
                      </div>
                      <div>
                        <span>Fecha límite</span>
                        <strong className="mono">
                          {dateLabel(selected.fecha_limite_respuesta)}
                        </strong>
                      </div>
                      <div>
                        <span>Turnado a</span>
                        <strong className="mono">
                          {selected.area_asignada}
                        </strong>
                      </div>
                      <p>
                        {selected.responsables_detalle ||
                          "Sin analista asignado"}
                      </p>
                    </div>
                    <div className="inspector-section">
                      <span className="field-title">DOCUMENTOS</span>
                      <DocumentButton
                        label="Oficio de entrada"
                        available={selected.documento_entrada_disponible}
                        referenced={selected.tiene_documento_entrada}
                        onClick={() =>
                          run(() =>
                            download(
                              `/oficios/${selected.id}/documentos/entrada`,
                              selected.documento_entrada_nombre ||
                                "entrada.pdf",
                            ),
                          )
                        }
                      />
                      <DocumentButton
                        label="Acuse de respuesta"
                        available={selected.acuse_respuesta_disponible}
                        referenced={selected.tiene_acuse_respuesta}
                        onClick={() =>
                          run(() =>
                            download(
                              `/oficios/${selected.id}/documentos/acuse`,
                              selected.acuse_respuesta_nombre || "acuse.pdf",
                            ),
                          )
                        }
                      />
                      {canDispatch(user) && (
                        <button
                          className="text-button"
                          onClick={() => documentRef.current?.click()}
                        >
                          + Cargar documento de entrada
                        </button>
                      )}
                      <input
                        type="file"
                        className="visually-hidden"
                        ref={documentRef}
                        accept="application/pdf,.pdf"
                        aria-label="Cargar documento de entrada"
                        tabIndex={-1}
                        onChange={(e) => {
                          uploadEntry(e.target.files?.[0]);
                          e.target.value = "";
                        }}
                      />
                    </div>
                    {selected.nota_atencion && (
                      <div className="inspector-section">
                        <span className="field-title">ATENCIÓN REGISTRADA</span>
                        <p>{selected.nota_atencion}</p>
                        <small className="mono">
                          {selected.oficio_respuesta_numero}
                        </small>
                      </div>
                    )}
                    <div className="inspector-links">
                      {canDispatch(user) && (
                        <button
                          className="text-button"
                          onClick={() =>
                            setCapture({
                              next: selected.folio_ssg,
                              record: selected,
                            })
                          }
                        >
                          Editar / Turnar
                        </button>
                      )}
                      <button
                        className="text-button"
                        onClick={() =>
                          run(async () =>
                            setAudit(
                              await api<Audit[]>(
                                `/oficios/${selected.id}/historial`,
                              ),
                            ),
                          )
                        }
                      >
                        Ver historial
                      </button>
                    </div>
                  </div>
                  <div className="inspector-foot">
                    {user.role !== "Auditor" && (
                      <button
                        className="button primary"
                        onClick={() => setAttention(true)}
                      >
                        <Icon name="check" />
                        Registrar atención / Subir acuse
                      </button>
                    )}
                    <button
                      className="button secondary"
                      onClick={() =>
                        run(() =>
                          download(
                            `/oficios/${selected.id}/volante-pdf`,
                            `volante-${selected.folio_ssg}.pdf`,
                          ),
                        )
                      }
                    >
                      <Icon name="download" />
                      Volante de turno
                    </button>
                  </div>
                </>
              ) : (
                <div className="empty-state">
                  <p>Selecciona un oficio para consultar su expediente.</p>
                </div>
              )}
            </aside>
          </div>
          <div className="workspace-footer">
            <span>
              SICOA-SSG <span className="mono">1.0</span> · Control de oficios,
              turnos y alertas
            </span>
            <span>
              Corte{" "}
              <b className="mono">
                {dateLabel(summary?.fecha_referencia || null)}
              </b>
            </span>
          </div>
        </main>
      </div>
      {mobileMenu && (
        <Modal title="Menú de operación" onClose={() => setMobileMenu(false)}>
          <nav
            className="modal-content mobile-navigation"
            aria-label="Navegación móvil"
          >
            <button
              className="button secondary"
              onClick={() => {
                setMobileMenu(false);
                setQuery("");
                setArea("");
                filter("");
              }}
            >
              Correspondencia
            </button>
            <button
              className="button secondary"
              onClick={() => {
                setMobileMenu(false);
                setDirectory(true);
              }}
            >
              Directorio
            </button>
            <button
              className="button secondary"
              onClick={() => {
                setMobileMenu(false);
                setReports(true);
              }}
            >
              Reportes y entrega
            </button>
            {["Administrador", "Auditor"].includes(user.role) && (
              <button
                className="button secondary"
                onClick={() => {
                  setMobileMenu(false);
                  run(async () => setAudit(await api<Audit[]>("/audit-logs")));
                }}
              >
                Bitácora
              </button>
            )}
          </nav>
        </Modal>
      )}
      {notice && (
        <div className="toast" role="status">
          <Icon name="check" />
          {notice}
          <button
            className="icon-button"
            aria-label="Cerrar notificación"
            onClick={() => setNotice("")}
          >
            <Icon name="close" />
          </button>
        </div>
      )}
      {capture && config && (
        <OficioForm
          config={config}
          people={people}
          nextFolio={capture.next}
          record={capture.record}
          onClose={() => setCapture(null)}
          onSaved={saved}
        />
      )}
      {attention && selected && config && (
        <AttentionForm
          record={selected}
          today={config.today}
          onClose={() => setAttention(false)}
          onSaved={saved}
        />
      )}
      {directory && (
        <Directory
          people={people}
          editable={canDispatch(user)}
          onClose={() => setDirectory(false)}
          onSaved={refreshPeople}
        />
      )}
      {audit && (
        <Modal
          title="Bitácora de operaciones"
          onClose={() => setAudit(null)}
          wide
        >
          <div className="modal-content audit-list">
            {audit.length ? (
              audit.map((item) => (
                <details key={item.id}>
                  <summary>
                    <strong>{item.action.replaceAll("_", " ")}</strong>
                    <span>{item.actor_username}</span>
                    <time className="mono">
                      {item.created_at.replace("T", " ").slice(0, 19)} UTC
                    </time>
                  </summary>
                  <div className="audit-snapshots">
                    <pre>{JSON.stringify(item.before_json, null, 2)}</pre>
                    <pre>{JSON.stringify(item.after_json, null, 2)}</pre>
                  </div>
                </details>
              ))
            ) : (
              <p>No hay movimientos registrados.</p>
            )}
          </div>
        </Modal>
      )}
      {reports && (
        <Modal title="Reportes y entrega" onClose={() => setReports(false)}>
          <div className="modal-content reports-list">
            <p className="muted">
              Documentos en una página Carta, listos para impresión.
            </p>
            <button
              className="report-option"
              onClick={() =>
                run(() => download("/reportes/alertas-pdf", "alertas-ssg.pdf"))
              }
            >
              <Icon name="alert" />
              <span>
                <strong>Semáforo ejecutivo y alertas</strong>
                <small>
                  12 pendientes prioritarios y cumplimiento por área.
                </small>
              </span>
              <Icon name="download" />
            </button>
            <button
              className="report-option"
              onClick={() =>
                run(() =>
                  download(
                    `/reportes/acuse-entrega-pdf${marked.length ? `?ids=${marked.join(",")}` : ""}`,
                    "acuse-entrega-ssg.pdf",
                  ),
                )
              }
            >
              <Icon name="file" />
              <span>
                <strong>Hoja de entrega física</strong>
                <small>
                  {marked.length
                    ? `${marked.length} oficios marcados en la bandeja.`
                    : "Primeros 10 oficios pendientes. Marca otros para generar un lote."}
                </small>
              </span>
              <Icon name="download" />
            </button>
            <button
              className="report-option"
              onClick={() =>
                run(() =>
                  download(
                    "/oficios/export-excel",
                    "correspondencia-2026.xlsx",
                  ),
                )
              }
            >
              <Icon name="inbox" />
              <span>
                <strong>Correspondencia completa</strong>
                <small>Excel con los registros permitidos para tu rol.</small>
              </span>
              <Icon name="download" />
            </button>
            {summary && (
              <div className="compliance">
                <h3>Cumplimiento por área</h3>
                {summary.gerencias.map((item) => (
                  <div key={item.area}>
                    <strong>{item.area}</strong>
                    <span className="mono">
                      {item.atendidos} / {item.total}
                    </span>
                    <span className="mono">{item.cumplimiento}%</span>
                  </div>
                ))}
                <small>
                  Atendidos entre oficios que requieren respuesta. Se excluyen
                  cancelados.
                </small>
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}

function DocumentButton({
  label,
  available,
  referenced,
  onClick,
}: {
  label: string;
  available: boolean;
  referenced: boolean;
  onClick: () => void;
}) {
  return (
    <div className="document-row">
      <Icon name="file" />
      <div>
        {available ? (
          <button className="text-button" onClick={onClick}>
            {label}
          </button>
        ) : (
          <strong>{label}</strong>
        )}
        <small>
          {available
            ? "PDF disponible"
            : referenced
              ? "Referencia importada · archivo sin cargar"
              : "Sin documento cargado"}
        </small>
      </div>
      {available && <Icon name="download" size={15} />}
    </div>
  );
}

function Directory({
  people,
  editable,
  onClose,
  onSaved,
}: {
  people: Person[];
  editable: boolean;
  onClose: () => void;
  onSaved: () => Promise<unknown>;
}) {
  const [search, setSearch] = useState("");
  const [person, setPerson] = useState<Person | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    const body = {
      nombre_mostrar: form.get("nombre_mostrar"),
      cargo: form.get("cargo"),
      dependencia_unidad: form.get("dependencia_unidad"),
      prefijo_oficio_frecuente: form.get("prefijo_oficio_frecuente"),
      ...(person ? { version: person.version } : {}),
    };
    try {
      const result = await api<Person>(
        person ? `/funcionarios/${person.id}` : "/funcionarios",
        { method: person ? "PATCH" : "POST", body: JSON.stringify(body) },
      );
      setPerson(result);
      setSaved("Directorio actualizado.");
      await onSaved();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="Directorio institucional" onClose={onClose} wide>
      <div className="modal-content directory-grid">
        <div>
          <label>
            Buscar funcionario
            <input value={search} onChange={(e) => setSearch(e.target.value)} />
          </label>
          <div className="people-list">
            {people
              .filter((p) =>
                p.nombre_mostrar
                  .toLocaleLowerCase()
                  .includes(search.toLocaleLowerCase()),
              )
              .map((item) => (
                <button
                  key={item.id}
                  onClick={() => {
                    setPerson(item);
                    setError("");
                    setSaved("");
                  }}
                  aria-pressed={person?.id === item.id}
                >
                  <strong>{item.nombre_mostrar}</strong>
                  <small>{item.cargo}</small>
                </button>
              ))}
          </div>
        </div>
        <form
          key={`${person?.id || "new"}-${person?.version || 0}`}
          onSubmit={submit}
        >
          {editable && (
            <button
              type="button"
              className="text-button"
              onClick={() => {
                setPerson(null);
                setSaved("");
              }}
            >
              + Nuevo funcionario
            </button>
          )}
          {error && (
            <div role="alert" className="error-box">
              {error}
            </div>
          )}
          {saved && <p role="status">{saved}</p>}
          <label>
            Nombre
            <input
              name="nombre_mostrar"
              required
              defaultValue={person?.nombre_mostrar || ""}
              readOnly={!editable}
            />
          </label>
          <label>
            Cargo
            <input
              name="cargo"
              defaultValue={person?.cargo || ""}
              readOnly={!editable}
            />
          </label>
          <label>
            Dependencia / unidad
            <input
              name="dependencia_unidad"
              defaultValue={person?.dependencia_unidad || ""}
              readOnly={!editable}
            />
          </label>
          <label>
            Prefijo frecuente de oficio
            <input
              className="mono"
              name="prefijo_oficio_frecuente"
              defaultValue={person?.prefijo_oficio_frecuente || ""}
              readOnly={!editable}
            />
          </label>
          {person && <p className="mono muted">Versión {person.version}</p>}
          {editable && (
            <button className="button primary" disabled={busy}>
              {busy ? "Guardando…" : "Guardar funcionario"}
            </button>
          )}
        </form>
      </div>
    </Modal>
  );
}
