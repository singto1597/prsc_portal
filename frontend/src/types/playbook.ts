// P.R. Playbooks — คู่มือสภานักเรียน ข้อมูล 6 เล่ม (หมวดหมู่)
// ไฟล์รูปภาพ + PDF ถูกวางไว้ใน public/playbooks/volN/ โดยตรง
// → Vite เสิร์ฟเป็น static asset (ไม่ผ่าน module bundler, ไม่ต้อง import)
// โค้ดคำนวณ URL เอง เช่น /playbooks/vol1/page-01.webp

export interface Playbook {
  id: string
  title: string
  description: string
  coverImage: string
  pdfUrl: string
  /** จำนวนหน้าที่มีไฟล์รูปอยู่จริง (page-01.webp … page-{totalPages}.webp) */
  totalPages: number
  /** เช่น '/playbooks/vol1/' */
  basePath: string
}

/**
 * Mock data 6 เล่ม
 * ⚠️ totalPages ต้องตรงกับจำนวนไฟล์ page-XX.webp ที่วางจริงใน public/playbooks/volN/
 * เช่น vol1 มี page-01.webp ถึง page-10.webp → totalPages = 10
 */
export const PLAYBOOKS: Playbook[] = [
  {
    id: 'vol1',
    title: 'วิชาการ',
    description: 'แนวทางด้านการเรียน การสอบ ทุนการศึกษา และแหล่งเรียนรู้ภายในโรงเรียน',
    coverImage: '/playbooks/vol1/cover.webp',
    pdfUrl: '/playbooks/vol1/playbook.pdf',
    totalPages: 7,
    basePath: '/playbooks/vol1/',
  },
  {
    id: 'vol2',
    title: 'ปฏิคม',
    description: 'การดูแลรักษาห้องเรียน สภาพแวดล้อม และสิ่งอำนวยความสะดวกต่างๆ พร้อมแนวทางการดูแลรักษา หรือแนวทางปฏิบัติเมื่อเกิดของชำรุด',
    coverImage: '/playbooks/vol2/cover.webp',
    pdfUrl: '/playbooks/vol2/playbook.pdf',
    totalPages: 17,
    basePath: '/playbooks/vol2/',
  },
  {
    id: 'vol3',
    title: 'กิจกรรม',
    description: 'กิจกรรมนักเรียน ชมรม และเทศกาลต่าง ๆ ของโรงเรียน พร้อมแนวทางเข้าร่วมอย่างมีความสุข',
    coverImage: '/playbooks/vol3/cover.webp',
    pdfUrl: '/playbooks/vol3/playbook.pdf',
    totalPages: 20,
    basePath: '/playbooks/vol3/',
  },
  {
    id: 'vol4',
    title: 'วินัย',
    description: 'ระเบียบวินัยและกติกาของโรงเรียนที่นักเรียนทุกคนควรทราบ พร้อมแนวปฏิบัติตนอย่างถูกต้อง',
    coverImage: '/playbooks/vol4/cover.webp',
    pdfUrl: '/playbooks/vol4/playbook.pdf',
    totalPages: 14,
    basePath: '/playbooks/vol4/',
  },
  {
    id: 'vol5',
    title: 'สุขภาวะ',
    description: 'การดูแลสุขภาพกายและใจ การจัดการความเครียด และการใช้ชีวิตอย่างสมดุลในวัยเรียน',
    coverImage: '/playbooks/vol5/cover.webp',
    pdfUrl: '/playbooks/vol5/playbook.pdf',
    totalPages: 17,
    basePath: '/playbooks/vol5/',
  },
  {
    id: 'vol6',
    title: 'ประชาธิปไตย',
    description: 'ประชาธิปไตยในโรงเรียน บทบาทของสภานักเรียน สิทธิและหน้าที่ของนักเรียน และการมีส่วนร่วม',
    coverImage: '/playbooks/vol6/cover.webp',
    pdfUrl: '/playbooks/vol6/playbook.pdf',
    totalPages: 19,
    basePath: '/playbooks/vol6/',
  },
]

export function getPlaybookById(id: string): Playbook | undefined {
  return PLAYBOOKS.find((p) => p.id === id)
}

/** เลขเล่มจาก id เช่น 'vol3' → '3' */
export function playbookVolume(id: string): string {
  const m = /^vol(\d+)$/.exec(id)
  return m?.[1] ?? id
}
