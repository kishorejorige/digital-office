export function EmptyState({ icon: Icon, title, description }: { icon: any; title: string; description: string }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-10 px-4">
      <div className="h-10 w-10 rounded-full bg-surface2/80 flex items-center justify-center mb-3 border border-borderSubtle">
        <Icon className="h-5 w-5 text-textSecondary" />
      </div>
      <p className="text-sm font-medium text-textPrimary">{title}</p>
      <p className="text-sm text-textSecondary mt-1 max-w-sm">{description}</p>
    </div>
  )
}
