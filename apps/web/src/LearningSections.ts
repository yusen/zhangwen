import { BookOpen, ClipboardList, FileText, Flag, FolderArchive, FolderOpen, Image, Lightbulb, NotebookPen, Settings2, Sparkles, Target, Trophy, type LucideIcon } from 'lucide-react';
import type { LearningRole, Material } from './LearningMaterials';

export type LearningSection = 'guidance' | 'project' | 'outcomes';
export type PreviewDialog = 'settings' | 'goals' | 'resources' | 'project';
type LearningAction = {icon: LucideIcon; title: string; hint: string; material?: Material; dialog?: PreviewDialog; pending?: boolean};
export const learningSections: {id: LearningSection; label: string; note?: string; icon: LucideIcon; description: string}[] = [
  {id:'guidance', label:'问题引导', icon:Lightbulb, description:'从想法出发，想清楚要解决的问题'},
  {id:'project', label:'项目学习', note:'PBL · 项目式学习', icon:BookOpen, description:'围绕目标，组织任务、实践与评价'},
  {id:'outcomes', label:'成果档案', icon:FolderArchive, description:'整理作品证据，准备展示与参赛材料'},
];
export const sectionMaterials: Record<LearningSection, Record<LearningRole, {id: Material; label: string}[]>> = {
  guidance: {
    teacher:[{id:'definition', label:'项目定义卡'}, {id:'questions', label:'问题记录'}],
    student:[{id:'definition', label:'项目定义卡'}, {id:'questions', label:'我的问题记录'}],
  },
  project: {
    teacher:[{id:'plan', label:'学习方案'}, {id:'task', label:'学生任务单'}, {id:'rubric', label:'评价量规'}, {id:'portfolio', label:'学习档案'}],
    student:[{id:'task', label:'我的任务'}, {id:'record', label:'探究记录'}, {id:'reflection', label:'自评与反思'}],
  },
  outcomes: {
    teacher:[{id:'portfolio', label:'成果总览'}, {id:'poster', label:'成果海报'}, {id:'competition', label:'赛事资料'}],
    student:[{id:'work', label:'作品说明'}, {id:'poster', label:'作品海报'}, {id:'competition', label:'参赛材料'}, {id:'portfolio', label:'我的档案'}],
  },
};
const guidanceActions: LearningAction[] = [
  {icon:Sparkles, title:'创意激发', hint:'从兴趣、主题或生活问题开始', pending:true},
  {icon:Target, title:'可行性研判', hint:'结合课时、器材与预算', pending:true},
  {icon:Settings2, title:'硬件匹配', hint:'比较想法与已有硬件', pending:true},
  {icon:FileText, title:'项目定义卡', hint:'问题、方案与待确认事项', material:'definition'},
];
export const sectionNavigation: Record<LearningSection, Record<LearningRole, LearningAction[]>> = {
  guidance: {teacher:guidanceActions, student:guidanceActions},
  project: {
    teacher:[
      {icon:Settings2, title:'学习设置', hint:'学段、课时与学情', dialog:'settings'},
      {icon:Target, title:'目标与任务', hint:'学习目标与活动', dialog:'goals'},
      {icon:FolderOpen, title:'教学资料', hint:'教材与课程参考', dialog:'resources'},
      {icon:BookOpen, title:'学习方案', hint:'三阶路径与课时安排', material:'plan'},
      {icon:Flag, title:'评价设计', hint:'观察点与反馈', material:'rubric'},
    ],
    student:[
      {icon:ClipboardList, title:'我的任务', hint:'看清问题与完成要求', material:'task'},
      {icon:NotebookPen, title:'探究记录', hint:'预测、测试与发现', material:'record'},
      {icon:Flag, title:'自评与反思', hint:'回看收获与同伴反馈', material:'reflection'},
    ],
  },
  outcomes: {
    teacher:[
      {icon:FolderArchive, title:'成果总览', hint:'回看学习证据与作品', material:'portfolio'},
      {icon:Image, title:'成果海报', hint:'活动与班级展示', material:'poster'},
      {icon:Trophy, title:'赛事资料', hint:'要求、清单与归档', material:'competition'},
    ],
    student:[
      {icon:FileText, title:'作品说明', hint:'讲清我的设计与证据', material:'work'},
      {icon:Image, title:'作品海报', hint:'作品介绍与探究展示', material:'poster'},
      {icon:Trophy, title:'参赛材料', hint:'跟着清单准备材料', material:'competition'},
      {icon:FolderArchive, title:'我的档案', hint:'整理作品与成长证据', material:'portfolio'},
    ],
  },
};
