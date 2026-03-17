import "./globals.css";

export const metadata = {
  title: "🌱 Sensor Monitor - Giám sát cảm biến nông nghiệp",
  description: "Hệ thống giám sát real-time 11 tham số cảm biến nông nghiệp với AI phân tích",
};

export default function RootLayout({ children }) {
  return (
    <html lang="vi">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600;700;800&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
