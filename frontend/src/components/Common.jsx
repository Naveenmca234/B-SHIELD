import Modal from './Modal'

export function ConfirmDialog({ open, title = 'Are you sure?', message, onConfirm, onCancel, danger }) {
  return (
    <Modal open={open} onClose={onCancel} title={title}>
      <p className="text-sm text-ops-muted mb-5">{message}</p>
      <div className="flex justify-end gap-2">
        <button onClick={onCancel} className="px-4 py-2 rounded-lg text-sm font-medium bg-white/5 hover:bg-white/10 text-ops-text">
          Cancel
        </button>
        <button
          onClick={onConfirm}
          className={`px-4 py-2 rounded-lg text-sm font-semibold ${
            danger ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30 border border-red-500/40' : 'bg-ops-accent/20 text-ops-accent2 hover:bg-ops-accent/30 border border-ops-accent/40'
          }`}
        >
          Confirm
        </button>
      </div>
    </Modal>
  )
}

export function Pagination({ page, pageSize, total, onPageChange }) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  return (
    <div className="flex items-center justify-between px-1 py-3 text-xs text-ops-muted">
      <span>Showing page {page} of {totalPages} ({total} total)</span>
      <div className="flex gap-1.5">
        <button
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
          className="px-3 py-1.5 rounded-md bg-white/5 hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed"
        >
          Prev
        </button>
        <button
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
          className="px-3 py-1.5 rounded-md bg-white/5 hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed"
        >
          Next
        </button>
      </div>
    </div>
  )
}
