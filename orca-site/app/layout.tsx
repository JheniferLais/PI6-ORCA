import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
    variable: "--font-geist-sans",
    subsets: ["latin"],
});

const geistMono = Geist_Mono({
    variable: "--font-geist-mono",
    subsets: ["latin"],
});

export const metadata: Metadata = {
    title: "ORCA | Sistema de Controlo Parental",
    description: "Plataforma inteligente de filtragem e segurança web baseada em IA e visão computacional.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html
            lang="pt"
            className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
        >
        <body className="min-h-full flex flex-col">{children}</body>
        </html>
    );
}
