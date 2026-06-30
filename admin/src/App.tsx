import { useEffect, useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import type { Session } from '@supabase/supabase-js'
import { supabase } from './lib/supabase'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import CallsList from './pages/CallsList'
import CallDetail from './pages/CallDetail'
import Orders from './pages/Orders'

function RequireAuth({ session, children }: { session: Session | null; children: React.ReactNode }) {
  if (!session) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  const [session, setSession] = useState<Session | null>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setReady(true)
    })
    const { data: sub } = supabase.auth.onAuthStateChange((_e, s) => setSession(s))
    return () => sub.subscription.unsubscribe()
  }, [])

  if (!ready) return null

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={session ? <Navigate to="/" replace /> : <Login />} />
        <Route
          element={
            <RequireAuth session={session}>
              <Layout />
            </RequireAuth>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="calls" element={<CallsList />} />
          <Route path="calls/:id" element={<CallDetail />} />
          <Route path="orders" element={<Orders />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
