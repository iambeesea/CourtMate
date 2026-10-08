import { Download, Share2 } from 'lucide-react'
import { useState } from 'react'
import { renderStory, type StoryData } from '../lib/story'
import { Modal } from './Modal'

function toBlob(canvas: HTMLCanvasElement) {
  return new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/png', 1))
}

function download(blob: Blob) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.download = 'courtmate-recap.png'
  link.href = url
  link.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

/**
 * Instagram Story sharing. The card is rendered to a 1080 × 1920 PNG in the browser and
 * handed to the phone's native share sheet; where files cannot be shared it downloads instead.
 */
export function StoryModal({ data, onClose }: { data: StoryData; onClose: () => void }) {
  const [sharing, setSharing] = useState(false)

  async function image(): Promise<Blob | null> {
    const canvas = renderStory(data)
    return canvas ? toBlob(canvas) : null
  }

  async function save() {
    const blob = await image()
    if (blob) download(blob)
  }

  async function share() {
    setSharing(true)
    const blob = await image()
    if (!blob) {
      setSharing(false)
      return
    }
    const file = new File([blob], 'courtmate-recap.png', { type: 'image/png' })
    const payload = { files: [file], title: 'My CourtMate recap', text: 'Made to play. Built to connect. #CourtMate' }
    try {
      if (typeof navigator.share === 'function' && (typeof navigator.canShare !== 'function' || navigator.canShare(payload))) {
        await navigator.share(payload)
      } else {
        download(blob)
      }
    } catch (error) {
      if (!(error instanceof DOMException && error.name === 'AbortError')) download(blob)
    } finally {
      setSharing(false)
    }
  }

  return (
    <Modal title="Share your recap" onClose={onClose} variant="dialog" wide>
      <div className="story-layout">
        <div className="story-card">
          <span className="story-brand">COURTMATE</span>
          <div className="story-ball" />
          <p>
            {data.title[0]}
            <br />
            {data.title[1]}
          </p>
          <strong>{data.headline}</strong>
          <span>{data.headlineLabel}</span>
          {data.lines.length > 0 && (
            <div className="story-box">
              {data.lines.map((text) => (
                <b key={text}>{text}</b>
              ))}
            </div>
          )}
          <small>{data.footer}</small>
        </div>
        <div className="story-actions">
          <h3>Your card is ready.</h3>
          <p>
            On your phone, choose <strong>Instagram</strong>, then <strong>Stories</strong> from the share sheet.
          </p>
          {data.demo && <p className="form-hint">These are demo figures, and the card says so.</p>}
          <button onClick={share} disabled={sharing}>
            <Share2 size={17} />
            {sharing ? 'Preparing story…' : 'Share to Instagram Story'}
          </button>
          <button className="download-button" onClick={save}>
            <Download size={17} /> Download PNG
          </button>
        </div>
      </div>
    </Modal>
  )
}
