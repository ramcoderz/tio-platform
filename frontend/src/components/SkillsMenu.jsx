import { motion, AnimatePresence } from 'framer-motion';
import { Plane, GraduationCap, Stethoscope, Code, ShoppingCart, FileText, Sparkles, X } from 'lucide-react';

const ALL_SKILLS = [
  // Tourism
  { id: 'tourism_planner', cmd: '/itinerary', name: 'Trip Planner', desc: 'Generate a full itinerary with tips and reviews.', icon: Plane, color: '#34D399', domains: ['tourism'] },
  { id: 'attraction_recommender', cmd: '/recommender', name: 'Top Attractions', desc: 'Find the best places to visit.', icon: Sparkles, color: '#10B981', domains: ['tourism'] },
  { id: 'ride_optimizer', cmd: '/optimize', name: 'Ride Optimizer', desc: 'Plan your attraction visits to skip queues.', icon: Sparkles, color: '#059669', domains: ['tourism'] },
  
  // Education
  { id: 'course_finder', cmd: '/coursefinder', name: 'Course Finder', desc: 'Match courses to your career goals.', icon: GraduationCap, color: '#A78BFA', domains: ['education'] },
  { id: 'admission_assistant', cmd: '/admission', name: 'Admission Help', desc: 'Guide through the application process.', icon: GraduationCap, color: '#8B5CF6', domains: ['education'] },
  { id: 'scholarship_helper', cmd: '/scholarship', name: 'Scholarship Finder', desc: 'Find funding and scholarships.', icon: Sparkles, color: '#7C3AED', domains: ['education'] },
  
  // Medical
  { id: 'dept_navigator', cmd: '/navigator', name: 'Department Guide', desc: 'Find the right medical department.', icon: Stethoscope, color: '#F87171', domains: ['medical'] },
  { id: 'appointment_guidance', cmd: '/appointment', name: 'Book Appointment', desc: 'Get guidance on booking a visit.', icon: Stethoscope, color: '#EF4444', domains: ['medical'] },
  { id: 'insurance_assistant', cmd: '/insurance', name: 'Insurance Help', desc: 'Clarify coverage and billing details.', icon: Stethoscope, color: '#DC2626', domains: ['medical'] },
  
  // Developer
  { id: 'api_assistant', cmd: '/apihelp', name: 'API Assistant', desc: 'Generate integration code from docs.', icon: Code, color: '#60A5FA', domains: ['developer'] },
  { id: 'integration_helper', cmd: '/integration', name: 'Integration Architect', desc: 'Design complex system flows.', icon: Code, color: '#3B82F6', domains: ['developer'] },
  { id: 'sdk_guide', cmd: '/sdk', name: 'SDK Guide', desc: 'Setup and usage guide for libraries.', icon: Code, color: '#2563EB', domains: ['developer'] },
  
  // Ecommerce
  { id: 'shopping_guide', cmd: '/shopping', name: 'Shopping Guide', desc: 'Product recommendations and comparisons.', icon: ShoppingCart, color: '#EC4899', domains: ['ecommerce'] },
  
  // General
  { id: 'doc_summarizer', cmd: '/summarize', name: 'Doc Summarizer', desc: 'Synthesize documents into key points.', icon: FileText, color: '#FBBF24', domains: ['general', 'education', 'medical', 'tourism', 'developer', 'ecommerce'] },
];

export default function SkillsMenu({ domain = 'general', onSelect, onClose }) {
  const relevantSkills = ALL_SKILLS.filter(s => s.domains.includes(domain) || s.domains.includes('general'));
  // Always show doc_summarizer as a fallback
  const skills = relevantSkills.length > 0 ? relevantSkills : ALL_SKILLS.filter(s => s.domains.includes('general'));

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95, y: 8 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95, y: 8 }}
      style={{
        position: 'absolute', bottom: '48px', left: '0',
        width: '300px', padding: '12px', zIndex: 50,
        background: 'var(--bg-card)', border: '1px solid var(--border)',
        borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-lg)'
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', padding: '0 4px' }}>
        <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Skills</span>
        <button onClick={onClose} style={{ color: 'var(--text-dim)', padding: '2px' }}><X size={14} /></button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        {skills.map(skill => (
          <button
            key={skill.id}
            onClick={() => onSelect(skill.id)}
            style={{
              display: 'flex', alignItems: 'center', gap: '10px',
              padding: '10px', borderRadius: 'var(--radius-sm)',
              textAlign: 'left', width: '100%',
              transition: 'background 0.15s'
            }}
            onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            <div style={{
              width: '34px', height: '34px', borderRadius: 'var(--radius-sm)',
              background: `${skill.color}18`, color: skill.color,
              display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
            }}>
              <skill.icon size={17} />
            </div>
            <div>
              <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>{skill.name}</div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', lineHeight: 1.3, marginTop: '1px' }}>{skill.desc}</div>
            </div>
          </button>
        ))}
      </div>

      <div style={{ marginTop: '8px', paddingTop: '8px', borderTop: '1px solid var(--border-light)', fontSize: '10px', color: 'var(--text-dim)', display: 'flex', alignItems: 'center', gap: '5px', padding: '4px' }}>
        <Sparkles size={10} color="var(--accent)" /> Workflow-aware skills
      </div>
    </motion.div>
  );
}
