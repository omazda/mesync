import React from 'react'

/* Фирменный знак MeSync: два узла (MAX/TG), соединённые «мостом» с бегущим потоком. */
export function Bridge() {
  return (
    <span className="bridge">
      <span className="node max" />
      <span className="span" />
      <span className="node tg" />
    </span>
  )
}
