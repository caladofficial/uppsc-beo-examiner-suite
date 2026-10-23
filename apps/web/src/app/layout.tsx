import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "UPPSC BEO Mains — Answer sheet check",
  description:
    "Check a UPPSC BEO Mains answer sheet against the model answer and see what is missing.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[#FAF6F3] text-[#484A47] selection:bg-[#E0AC9D] selection:text-[#484A47]">
        {children}
      </body>
    </html>
  );
}
