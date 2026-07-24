import type { ReactNode } from 'react'
import type { Metadata, Viewport } from 'next'
import Link from 'next/link'
import './globals.css'

export const metadata: Metadata = {
  title: 'Vercel + Valkey Streams Message Queue',
  description: 'A Next.js demo using Valkey Streams for reliable message queuing',
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="mx-auto h-screen flex flex-col">
          <nav className="border-b border-gray-200 py-5 bg-white shadow-sm">
            <div className="flex items-center px-8 mx-auto max-w-7xl">
              <Link href="/" className="font-semibold text-gray-900">
                Valkey Streams Message Queue
              </Link>
              <div className="flex-1 justify-end hidden md:flex">
                <Link
                  href="/process"
                  className="text-sm text-gray-500 hover:text-gray-900 px-3 py-2"
                >
                  Process Messages →
                </Link>
              </div>
            </div>
          </nav>

          <div className="px-8 bg-white flex-1">
            {children}
          </div>

          <footer className="py-6 w-full mt-auto border-t flex items-center justify-center bg-gray-50">
            <span className="text-sm text-gray-500">
              Built with{' '}
              <a href="https://valkey.io" className="underline hover:text-gray-900" target="_blank" rel="noreferrer">
                Valkey
              </a>
              {' + '}
              <a href="https://nextjs.org" className="underline hover:text-gray-900" target="_blank" rel="noreferrer">
                Next.js
              </a>
            </span>
          </footer>
        </div>
      </body>
    </html>
  )
}
