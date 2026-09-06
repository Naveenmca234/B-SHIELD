import Sidebar from './Sidebar'
import Header from './Header'

export default function Layout({ title, subtitle, wsStatus, alertCount, children }) {
  return (
    <div className="flex min-h-screen bg-ops-bg">
      <Sidebar />
      <div className="flex-1 min-w-0 flex flex-col">
        <Header title={title} subtitle={subtitle} wsStatus={wsStatus} alertCount={alertCount} />
        <main className="flex-1 p-6 overflow-x-hidden">{children}</main>
      </div>
    </div>
  )
}
