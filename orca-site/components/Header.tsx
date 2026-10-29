import Image from "next/image";
import Link from "next/link";

const links = [
  { href: "/", label: "Início" },
  { href: "/logs", label: "Logs" },
  { href: "/login", label: "Entrar" },
];

export default function Header() {
  return (
    <header className="border-b border-black/10 dark:border-white/15">
      <nav className="mx-auto flex w-full max-w-5xl items-center justify-between px-6 py-4">
        <Link href="/" className="flex items-center gap-2 font-semibold">
          <Image src="/orca-logo.png" alt="" width={32} height={32} />
          ORCA
        </Link>

        <ul className="flex items-center gap-6 text-sm">
          {links.map((link) => (
            <li key={link.href}>
              <Link href={link.href} className="hover:underline">
                {link.label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </header>
  );
}
