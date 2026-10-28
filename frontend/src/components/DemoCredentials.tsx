"use client";

type DemoAccount = {
  role: string;
  email: string;
  password: string;
  hint: string;
};

const ACCOUNTS: DemoAccount[] = [
  {
    role: "Docente",
    email: "docente@demo.sapia.cl",
    password: "Sapia2026!",
    hint: "Flujo completo MitL",
  },
  {
    role: "Coordinador PIE",
    email: "pie@demo.sapia.cl",
    password: "Sapia2026!",
    hint: "Panel seguimiento y exportación",
  },
];

type Props = {
  onSelect: (email: string, password: string) => void;
};

export function DemoCredentials({ onSelect }: Props) {
  return (
    <div className="demo-creds">
      <p className="demo-creds-title">Acceso demo — Proyecto de título INACAP</p>
      <div className="demo-creds-grid">
        {ACCOUNTS.map((a) => (
          <button
            key={a.email}
            type="button"
            className="demo-cred-card"
            onClick={() => onSelect(a.email, a.password)}
          >
            <span className="demo-cred-role">{a.role}</span>
            <span className="demo-cred-email">{a.email}</span>
            <span className="demo-cred-hint">{a.hint}</span>
          </button>
        ))}
      </div>
      <p className="demo-creds-foot">Contraseña demo: <code>Sapia2026!</code></p>
    </div>
  );
}
