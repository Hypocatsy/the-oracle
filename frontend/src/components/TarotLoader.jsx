import { useState, useEffect, useRef } from 'react'
import cardBack from '../assets/card-back.png'
import theStar from '../assets/cards/the-star.png'
import theWorld from '../assets/cards/the-world.png'
import theTower from '../assets/cards/the-tower.png'
import '../styles/TarotLoader.css'

const FRONT_CARDS = [theStar, theWorld, theTower]

const MESSAGES = [
  'Consulting the cards\u2026',
  'The Oracle is reading\u2026',
  'Divining your answer\u2026',
  'The stars are aligning\u2026',
  'Channeling ancient wisdom\u2026',
]

const SPARKLE_COUNT = 8

function pickRandom(arr, exclude) {
  const choices = arr.filter(item => item !== exclude)
  return choices[Math.floor(Math.random() * choices.length)]
}

export default function TarotLoader() {
  const [frontCard, setFrontCard] = useState(() =>
    FRONT_CARDS[Math.floor(Math.random() * FRONT_CARDS.length)]
  )
  const [message, setMessage] = useState(() =>
    MESSAGES[Math.floor(Math.random() * MESSAGES.length)]
  )
  const prevCard = useRef(frontCard)
  const prevMsg = useRef(message)

  useEffect(() => {
    const interval = setInterval(() => {
      const newCard = pickRandom(FRONT_CARDS, prevCard.current)
      const newMsg = pickRandom(MESSAGES, prevMsg.current)
      setFrontCard(newCard)
      setMessage(newMsg)
      prevCard.current = newCard
      prevMsg.current = newMsg
    }, 2500)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="tarot-loader">
      <div className="tarot-card-scene">
        <div className="tarot-card" key={frontCard}>
          <div className="tarot-card-face back">
            <img src={cardBack} alt="Card back" />
          </div>
          <div className="tarot-card-face front">
            <img src={frontCard} alt="Tarot card" />
          </div>
        </div>
        <div className="tarot-sparkles">
          {Array.from({ length: SPARKLE_COUNT }, (_, i) => (
            <span key={i} className="tarot-sparkle">✦</span>
          ))}
        </div>
      </div>
      <p className="tarot-message">{message}</p>
    </div>
  )
}
