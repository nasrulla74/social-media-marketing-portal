import "./globals.css";

export const metadata = {
  title: "Marketing Portal MVP",
  description: "Customer onboarding and approval portal",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
