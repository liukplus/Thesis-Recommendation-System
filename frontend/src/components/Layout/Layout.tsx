import { ReactNode } from 'react'
import Navbar from './Navbar'
import './Layout.css'

interface LayoutProps {
  children: ReactNode
}

export default function Layout({ children }: LayoutProps) {
  return (
    <div className="app-layout">
      <Navbar />
      <main className="app-main">{children}</main>
      <footer className="app-footer">
        <p>Thesis Recommendation System v0.1.0 — Built with FastAPI + React</p>
      </footer>
    </div>
  )
}
