import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { supabase } from '../lib/supabase'

export default function Layout() {
  const navigate = useNavigate()

  async function signOut() {
    await supabase.auth.signOut()
    navigate('/login')
  }

  return (
    <div className="layout">
      <aside className="sidebar">
        <h1>Sierra Admin<br /><small style={{ color: '#888', fontWeight: 400 }}>Bizbull</small></h1>
        <nav>
          <NavLink to="/" end>Overview</NavLink>
          <NavLink to="/calls">Calls</NavLink>
          <NavLink to="/orders">Orders</NavLink>
        </nav>
        <button type="button" className="secondary" style={{ marginTop: '2rem', width: '100%' }} onClick={signOut}>
          Sign out
        </button>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}
