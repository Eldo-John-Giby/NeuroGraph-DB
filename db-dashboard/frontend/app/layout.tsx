import type { Metadata } from "next";
import "./globals.css";
import "./workspace-refresh.css";
import "./comparison.css";
import "./result-clarity.css";
import { AuthProvider } from "./context/AuthContext";

export const metadata: Metadata = {
  title: "NeuroGraph — Review intelligence",
  description: "Verified graph neural network results, product review analysis, and saved evidence.",
  icons: { icon: [{ url: '/icon.svg?v=2', type: 'image/svg+xml' }, { url: '/favicon.ico?v=2', sizes: '32x32' }], apple: '/apple-touch-icon.png' },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased selection:bg-teal-200 selection:text-slate-900">
        <AuthProvider>
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}
