import { useCart } from '../hooks/useCart'
import type { OrderStatus } from '../lib/api'

interface Props {
  connected: boolean
}

const STATUS_LABEL: Record<OrderStatus, string> = {
  empty: 'Building your order',
  building: 'Building your order',
  awaiting_contact: 'Almost there — Sierra needs your details',
  confirming: 'Ready to confirm',
  placed: 'Order placed',
}

export function OrderPanel({ connected }: Props) {
  const { state, ready, setQty, removeItem } = useCart()
  const items = state?.items ?? []
  const placed = state?.status === 'placed'

  if (items.length === 0) {
    return (
      <section className="panel order-panel" aria-label="Your order">
        <div className="panel-title">Your Order</div>
        <div className="order-empty">
          {connected
            ? 'Your items will appear here as you order with Sierra — by voice, or adjust quantities here once they land.'
            : 'Start a call and order by voice — your cart updates live here.'}
        </div>
      </section>
    )
  }

  return (
    <section className="panel order-panel" aria-label="Your order">
      <div className="panel-title">Your Order</div>

      <div className={`order-status status-${state?.status ?? 'building'}`}>
        {STATUS_LABEL[state?.status ?? 'building']}
        {placed && state?.eta ? ` · ready in ${state.eta}` : ''}
      </div>

      <ul className="order-items">
        {items.map((item, idx) => {
          const key = item.id ?? `${item.name}-${idx}`
          return (
            <li key={key} className="order-item">
              <div className="oi-main">
                <span className="oi-name">{item.name}</span>
                {item.note && <span className="oi-note">{item.note}</span>}
              </div>
              <div className="oi-right">
                {!placed && item.id ? (
                  <div className="qty-stepper" role="group" aria-label={`Quantity for ${item.name}`}>
                    <button
                      className="qty-btn"
                      aria-label="Decrease quantity"
                      disabled={!ready}
                      onClick={() => setQty(item.id as string, item.qty - 1)}
                    >
                      −
                    </button>
                    <span className="qty-val">{item.qty}</span>
                    <button
                      className="qty-btn"
                      aria-label="Increase quantity"
                      disabled={!ready}
                      onClick={() => setQty(item.id as string, item.qty + 1)}
                    >
                      +
                    </button>
                  </div>
                ) : (
                  <span className="oi-qty">×{item.qty}</span>
                )}
                <span className="oi-price">${item.line_total.toFixed(2)}</span>
                {!placed && item.id && (
                  <button
                    className="oi-remove"
                    aria-label={`Remove ${item.name}`}
                    disabled={!ready}
                    onClick={() => removeItem(item.id as string)}
                  >
                    ×
                  </button>
                )}
              </div>
            </li>
          )
        })}
      </ul>

      <div className="order-totals">
        <div className="ot-row">
          <span>Subtotal</span>
          <span>${(state?.subtotal ?? 0).toFixed(2)}</span>
        </div>
        {state?.order_type === 'delivery' && (state?.delivery_charge ?? 0) > 0 && (
          <div className="ot-row">
            <span>Delivery</span>
            <span>${(state?.delivery_charge ?? 0).toFixed(2)}</span>
          </div>
        )}
        <div className="ot-row ot-total">
          <span>Total</span>
          <span>${(state?.total ?? 0).toFixed(2)}</span>
        </div>
      </div>

      {(state?.order_type || state?.customer.name) && (
        <div className="order-meta">
          {state?.order_type && (
            <span className="om-pill">{state.order_type === 'delivery' ? 'Delivery' : 'Pickup'}</span>
          )}
          {state?.customer.name && <span className="om-line">{state.customer.name}</span>}
          {state?.customer.phone && <span className="om-line">{state.customer.phone}</span>}
          {state?.order_type === 'delivery' && state?.delivery_address && (
            <span className="om-line">{state.delivery_address}</span>
          )}
        </div>
      )}

      {placed && (
        <div className="order-placed-note">
          Pay at {state?.order_type === 'delivery' ? 'delivery' : 'pickup'}. Thank you!
        </div>
      )}
    </section>
  )
}
