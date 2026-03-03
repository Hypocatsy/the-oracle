import { motion, useReducedMotion } from 'framer-motion'
import '../styles/FloatingDecorations.css'

const DECORATIONS = [
  { char: '✦', x: '5%', y: '8%', size: 14, color: '#d4a574' },
  { char: '☽', x: '92%', y: '12%', size: 18, color: '#c4b5e0' },
  { char: '✧', x: '15%', y: '25%', size: 10, color: '#f5c6d0' },
  { char: '✦', x: '88%', y: '30%', size: 12, color: '#d4a574' },
  { char: '✧', x: '8%', y: '45%', size: 16, color: '#c4b5e0' },
  { char: '☽', x: '95%', y: '50%', size: 14, color: '#f5c6d0' },
  { char: '✦', x: '3%', y: '65%', size: 11, color: '#f5c6d0' },
  { char: '✧', x: '90%', y: '68%', size: 13, color: '#d4a574' },
  { char: '☽', x: '12%', y: '78%', size: 16, color: '#c4b5e0' },
  { char: '✦', x: '85%', y: '82%', size: 10, color: '#f5c6d0' },
  { char: '✧', x: '50%', y: '5%', size: 12, color: '#d4a574' },
  { char: '✦', x: '30%', y: '90%', size: 14, color: '#c4b5e0' },
  { char: '☽', x: '70%', y: '88%', size: 11, color: '#d4a574' },
  { char: '✧', x: '42%', y: '92%', size: 10, color: '#f5c6d0' },
  { char: '✦', x: '60%', y: '15%', size: 13, color: '#c4b5e0' },
  { char: '✧', x: '25%', y: '55%', size: 11, color: '#d4a574' },
  { char: '☽', x: '78%', y: '42%', size: 15, color: '#f5c6d0' },
  { char: '✦', x: '55%', y: '72%', size: 12, color: '#c4b5e0' },
]

export default function FloatingDecorations() {
  const prefersReduced = useReducedMotion()

  if (prefersReduced) return null

  return (
    <div className="floating-decorations">
      {DECORATIONS.map((d, i) => (
        <motion.span
          key={i}
          className="floating-item"
          style={{
            left: d.x,
            top: d.y,
            fontSize: d.size,
            color: d.color,
          }}
          animate={{
            y: [0, -10, 0, 10, 0],
            opacity: [0.3, 0.8, 1, 0.8, 0.3],
          }}
          transition={{
            duration: 4 + (i % 3),
            repeat: Infinity,
            delay: i * 0.3,
            ease: 'easeInOut',
          }}
        >
          {d.char}
        </motion.span>
      ))}
    </div>
  )
}
