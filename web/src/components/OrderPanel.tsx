interface Props {
  connected: boolean
}

// W1 stub. Live cart syncing (order.state push + get_order_state RPC) lands in W2.
export function OrderPanel({ connected }: Props) {
  return (
    <section className="panel order-panel" aria-label="Your order">
      <div className="panel-title">Your Order</div>
      <div className="order-empty">
        {connected
          ? 'Your items will appear here as you order with Sierra.'
          : 'Start a call and order by voice — your cart will update live here.'}
      </div>
    </section>
  )
}
