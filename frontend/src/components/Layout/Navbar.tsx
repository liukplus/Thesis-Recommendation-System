import { Link, NavLink } from 'react-router-dom'
import './Navbar.css'

export default function Navbar() {
  const navLinks = [
    { to: '/', label: 'Home', end: true },
    { to: '/search', label: 'Search' },
    { to: '/agent', label: 'Agent' },
    { to: '/settings', label: 'Settings' },
  ]

  return (
    <nav className="navbar">
      <div className="navbar-inner">
        <Link to="/" className="navbar-brand">
          <span className="brand-icon">📚</span>
          <span className="brand-text">Thesis RecSys</span>
        </Link>

        <div className="navbar-links">
          {navLinks.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              className={({ isActive }) =>
                `nav-link ${isActive ? 'active' : ''}`
              }
            >
              {link.label}
            </NavLink>
          ))}
        </div>
      </div>
    </nav>
  )
}
