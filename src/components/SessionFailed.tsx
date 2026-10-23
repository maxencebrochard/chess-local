// Message d'une séance demandée depuis un hub et impossible à construire (useSessionFailed.ts).
export function SessionFailed({ children }: { children: string }) {
  return (
    <p role="alert" data-testid="session-failed" className="mb-4 rounded bg-red-900/40 px-3 py-2 text-sm text-red-200">
      {children}
    </p>
  )
}
