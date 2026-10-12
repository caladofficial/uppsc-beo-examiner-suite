import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "UPPSC BEO Mains — Answer-Sheet Scanner & Rubric Evaluation Suite",
  description:
    "Production-minded examiner workstation for UPPSC Block Education Officer (BEO) Mains handwritten Hindi & English answer-sheet scanning, zero-context OCR/HTR transcription, and deterministic rubric-bounded grading.",
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
