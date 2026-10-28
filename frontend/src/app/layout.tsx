import "./globals.css";

export const metadata = {
  title: "SAPIA — Apoyo pedagógico con IA",
  description: "Sistema de Apoyo Pedagógico basado en IA para docentes con estudiantes neurodivergentes",
  icons: {
    icon: "/favicon.ico",
    apple: "/favicon-180.png",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
