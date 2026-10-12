import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "UPPSC BEO Mains — Answer-sheet grading",
  description:
    "Answer-sheet grading workspace for UPPSC BEO Mains examiners: papers, scans, handwriting review and marks.",
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
