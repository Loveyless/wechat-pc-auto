import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  BookOpen,
  Search,
  Star,
  Trash2,
  Edit3,
  Play,
  Check,
  X,
  ChevronLeft,
  Volume2,
} from "lucide-react";
import { useWordBookStore } from "@/stores/wordBookStore";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { WordMeaningsCard } from "@/components/WordMeaningDisplay";
import * as api from "@/lib/tauri-api";
import type { FavoriteWord, Meaning } from "@/lib/tauri-api";

// 播放单词发音的 hook（使用音频缓存）
function useWordAudio() {
  const [playing, setPlaying] = useState(false);
  const audioRef = { current: null as HTMLAudioElement | null };

  const playWord = async (word: string) => {
    if (playing) return;
    setPlaying(true);
    try {
      // 获取词典条目
      const entry = await api.wordLookup(word);
      const audioUrl = entry.phonetics.find((p) => p.audio_url)?.audio_url;
      if (audioUrl) {
        if (audioRef.current) {
          audioRef.current.pause();
        }
        // 通过 Tauri 获取缓存后的本地路径，再转换为 asset:// 协议
        const assetUrl = await api.audioGetAssetUrl(audioUrl);
        audioRef.current = new Audio(assetUrl);
        audioRef.current.onended = () => setPlaying(false);
        audioRef.current.onerror = () => setPlaying(false);
        audioRef.current.play().catch(() => setPlaying(false));
      } else {
        setPlaying(false);
      }
    } catch {
      setPlaying(false);
    }
  };

  return { playing, playWord };
}

interface WordCardProps {
  word: FavoriteWord;
  onDelete: () => void;
  onUpdateNote: (note: string) => void;
  onClick: () => void;
}

function WordCard({ word, onDelete, onUpdateNote, onClick }: WordCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [noteInput, setNoteInput] = useState(word.note || "");
  const { playing, playWord } = useWordAudio();

  const meanings: Meaning[] = word.meanings_json
    ? JSON.parse(word.meanings_json)
    : [];

  const getMasteryBadge = () => {
    switch (word.mastery_level) {
      case 2:
        return <Badge className="bg-green-500">已掌握</Badge>;
      case 1:
        return <Badge className="bg-yellow-500">复习中</Badge>;
      default:
        return <Badge className="bg-gray-500">待复习</Badge>;
    }
  };

  const handleSaveNote = () => {
    onUpdateNote(noteInput);
    setIsEditing(false);
  };

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className="p-4 rounded-lg border bg-card hover:shadow-md transition-shadow cursor-pointer"
      onClick={onClick}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <Star className="w-4 h-4 fill-yellow-400 text-yellow-400" />
          <span className="font-semibold text-lg text-foreground">{word.word}</span>
          {word.phonetic && (
            <span className="text-sm text-muted-foreground">
              {word.phonetic}
            </span>
          )}
          <button
            onClick={(e) => { e.stopPropagation(); playWord(word.word); }}
            className="p-1 rounded hover:bg-accent transition-colors"
            title="播放发音"
          >
            <Volume2 className={`w-3.5 h-3.5 ${playing ? "text-primary animate-pulse" : "text-muted-foreground"}`} />
          </button>
        </div>
        <div className="flex items-center gap-1">
          {getMasteryBadge()}
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={(e) => { e.stopPropagation(); setIsEditing(!isEditing); }}
          >
            <Edit3 className="w-3.5 h-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-destructive hover:text-destructive"
            onClick={(e) => { e.stopPropagation(); onDelete(); }}
          >
            <Trash2 className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>

      {/* 释义卡片（紧凑模式） */}
      <div className="mb-2">
        <WordMeaningsCard
          meanings={meanings}
          summaryZh={word.summary_zh || undefined}
          compact={true}
        />
      </div>

      {/* 笔记 */}
      {isEditing ? (
        <div className="flex items-center gap-2 mt-2">
          <Input
            value={noteInput}
            onChange={(e) => setNoteInput(e.target.value)}
            placeholder="添加笔记..."
            className="h-8 text-sm"
          />
          <Button size="sm" className="h-8" onClick={handleSaveNote}>
            <Check className="w-3.5 h-3.5" />
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-8"
            onClick={() => setIsEditing(false)}
          >
            <X className="w-3.5 h-3.5" />
          </Button>
        </div>
      ) : word.note ? (
        <p className="text-xs text-muted-foreground mt-2 italic">
          📝 {word.note}
        </p>
      ) : null}

      {/* 统计 */}
      <div className="flex items-center gap-4 mt-3 text-xs text-muted-foreground">
        <span>复习 {word.review_count} 次</span>
        {word.last_review_at && (
          <span>
            上次: {new Date(word.last_review_at).toLocaleDateString()}
          </span>
        )}
        <span>
          收藏于 {new Date(word.created_at).toLocaleDateString()}
        </span>
      </div>
    </motion.div>
  );
}

interface WordDetailProps {
  word: FavoriteWord;
  onClose: () => void;
  onUpdateNote: (note: string) => void;
  onDelete: () => void;
}

function WordDetail({ word, onClose, onUpdateNote, onDelete }: WordDetailProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [noteInput, setNoteInput] = useState(word.note || "");
  const { playing, playWord } = useWordAudio();

  // 直接使用收藏数据（已通过 JOIN 查询获取最新释义）
  const meanings: Meaning[] = word.meanings_json
    ? JSON.parse(word.meanings_json)
    : [];
  const summaryZh = word.summary_zh;

  const getMasteryLabel = () => {
    switch (word.mastery_level) {
      case 2: return { text: "已掌握", color: "bg-green-500" };
      case 1: return { text: "复习中", color: "bg-yellow-500" };
      default: return { text: "待复习", color: "bg-gray-500" };
    }
  };

  const mastery = getMasteryLabel();

  const handleSaveNote = () => {
    onUpdateNote(noteInput);
    setIsEditing(false);
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border">
        <Button variant="ghost" size="sm" onClick={onClose} className="text-foreground">
          <ChevronLeft className="w-4 h-4 mr-1" />
          返回
        </Button>
        <Badge className={mastery.color}>{mastery.text}</Badge>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 text-destructive hover:text-destructive"
          onClick={() => { onDelete(); onClose(); }}
        >
          <Trash2 className="w-4 h-4" />
        </Button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {/* Word & Phonetic */}
        <div className="text-center mb-6">
          <div className="flex items-center justify-center gap-2 mb-2">
            <Star className="w-5 h-5 fill-yellow-400 text-yellow-400" />
            <h1 className="text-2xl font-bold text-foreground">{word.word}</h1>
            <button
              onClick={() => playWord(word.word)}
              className="p-1.5 rounded-full hover:bg-accent transition-colors"
              title="播放发音"
            >
              <Volume2 className={`w-5 h-5 ${playing ? "text-primary animate-pulse" : "text-muted-foreground"}`} />
            </button>
          </div>
          {word.phonetic && (
            <p className="text-muted-foreground">{word.phonetic}</p>
          )}
        </div>

        {/* 释义卡片（完整模式，数据已通过 JOIN 查询获取最新） */}
        <div className="p-4 rounded-lg bg-muted/30 mb-6">
          <WordMeaningsCard
            meanings={meanings}
            summaryZh={summaryZh}
            maxDefinitions={10}
            showExample={true}
            showSynonyms={true}
          />
        </div>

        {/* Note */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-foreground">笔记</span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsEditing(!isEditing)}
              className="h-7"
            >
              <Edit3 className="w-3.5 h-3.5 mr-1" />
              {isEditing ? "取消" : "编辑"}
            </Button>
          </div>
          {isEditing ? (
            <div className="space-y-2">
              <Input
                value={noteInput}
                onChange={(e) => setNoteInput(e.target.value)}
                placeholder="添加笔记..."
                className="text-sm"
              />
              <Button size="sm" onClick={handleSaveNote}>
                <Check className="w-3.5 h-3.5 mr-1" />
                保存
              </Button>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground italic">
              {word.note || "暂无笔记"}
            </p>
          )}
        </div>

        {/* Stats */}
        <div className="p-3 rounded-lg bg-muted/30 space-y-2 text-sm">
          <div className="flex justify-between text-foreground">
            <span>复习次数</span>
            <span>{word.review_count} 次</span>
          </div>
          <div className="flex justify-between text-foreground">
            <span>连续正确</span>
            <span>{word.consecutive_correct} 次</span>
          </div>
          {word.last_review_at && (
            <div className="flex justify-between text-foreground">
              <span>上次复习</span>
              <span>{new Date(word.last_review_at).toLocaleDateString()}</span>
            </div>
          )}
          {word.next_review_at && (
            <div className="flex justify-between text-foreground">
              <span>下次复习</span>
              <span>{new Date(word.next_review_at).toLocaleDateString()}</span>
            </div>
          )}
          <div className="flex justify-between text-muted-foreground">
            <span>收藏时间</span>
            <span>{new Date(word.created_at).toLocaleDateString()}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

interface FlashcardReviewProps {
  onClose: () => void;
}

function FlashcardReview({ onClose }: FlashcardReviewProps) {
  const {
    currentSession,
    reviewWords,
    currentWordIndex,
    submitFeedback,
    nextWord,
    finishReview,
  } = useWordBookStore();

  const [showAnswer, setShowAnswer] = useState(false);
  const [startTime, setStartTime] = useState(Date.now());
  const { playing, playWord } = useWordAudio();

  const currentWord = reviewWords[currentWordIndex];
  const isLastWord = currentWordIndex >= reviewWords.length - 1;
  const progress =
    currentSession?.completed_words ?? 0 / (currentSession?.total_words ?? 1);

  const meanings: Meaning[] = currentWord?.meanings_json
    ? JSON.parse(currentWord.meanings_json)
    : [];

  useEffect(() => {
    setShowAnswer(false);
    setStartTime(Date.now());
  }, [currentWordIndex]);

  const handleFeedback = async (feedback: number) => {
    const responseTime = Date.now() - startTime;
    await submitFeedback(feedback, responseTime);

    if (isLastWord) {
      const session = await finishReview();
      if (session) {
        alert(
          `复习完成！\n✓ 认识: ${session.correct_count}\n? 模糊: ${session.fuzzy_count}\n✗ 不认识: ${session.wrong_count}`
        );
        onClose();
      }
    } else {
      nextWord();
    }
  };

  if (!currentWord) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-muted-foreground">没有待复习的单词</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border">
        <Button variant="ghost" size="sm" onClick={onClose} className="text-foreground">
          <ChevronLeft className="w-4 h-4 mr-1" />
          返回
        </Button>
        <span className="text-sm text-foreground">
          {currentWordIndex + 1} / {reviewWords.length}
        </span>
        <div className="w-20" />
      </div>

      {/* Progress */}
      <div className="h-1 bg-muted">
        <div
          className="h-full bg-primary transition-all"
          style={{ width: `${progress * 100}%` }}
        />
      </div>

      {/* Card */}
      <div className="flex-1 flex flex-col items-center justify-center p-8">
        <motion.div
          key={currentWordIndex}
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="w-full max-w-md"
        >
          {/* Word */}
          <div className="text-center mb-8">
            <div className="flex items-center justify-center gap-3 mb-2">
              <h2 className="text-3xl font-bold text-foreground">{currentWord.word}</h2>
              <button
                onClick={() => playWord(currentWord.word)}
                className="p-2 rounded-full hover:bg-accent transition-colors"
                title="播放发音"
              >
                <Volume2 className={`w-6 h-6 ${playing ? "text-primary animate-pulse" : "text-muted-foreground"}`} />
              </button>
            </div>
            {currentWord.phonetic && (
              <p className="text-muted-foreground">{currentWord.phonetic}</p>
            )}
          </div>

          {/* Answer */}
          {showAnswer ? (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="w-full p-4 rounded-lg bg-muted/30 mb-8"
            >
              <WordMeaningsCard
                meanings={meanings}
                summaryZh={currentWord.summary_zh || undefined}
                maxDefinitions={2}
                showExample={true}
                showSynonyms={false}
              />
            </motion.div>
          ) : (
            <Button
              variant="outline"
              size="lg"
              className="w-full mb-8 text-foreground border-border"
              onClick={() => setShowAnswer(true)}
            >
              点击显示释义
            </Button>
          )}

          {/* Feedback Buttons */}
          {showAnswer && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex gap-3"
            >
              <Button
                variant="outline"
                className="flex-1 border-red-500 text-red-500 hover:bg-red-500/10"
                onClick={() => handleFeedback(0)}
              >
                不认识
              </Button>
              <Button
                variant="outline"
                className="flex-1 border-yellow-500 text-yellow-500 hover:bg-yellow-500/10"
                onClick={() => handleFeedback(1)}
              >
                模糊
              </Button>
              <Button
                variant="outline"
                className="flex-1 border-green-500 text-green-500 hover:bg-green-500/10"
                onClick={() => handleFeedback(2)}
              >
                认识
              </Button>
            </motion.div>
          )}
        </motion.div>
      </div>
    </div>
  );
}

export function WordBook() {
  const {
    wordList,
    totalCount,
    loading,
    stats,
    isReviewing,
    fetchWordList,
    fetchStats,
    deleteWord,
    updateNote,
    startReview,
    cancelReview,
  } = useWordBookStore();

  const [searchQuery, setSearchQuery] = useState("");
  const [selectedWord, setSelectedWord] = useState<FavoriteWord | null>(null);

  useEffect(() => {
    fetchWordList();
    fetchStats();
  }, [fetchWordList, fetchStats]);

  const filteredWords = searchQuery
    ? wordList.filter((w) =>
        w.word.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : wordList;

  const handleStartReview = () => {
    startReview("flashcard", 20);
  };

  if (isReviewing) {
    return <FlashcardReview onClose={cancelReview} />;
  }

  if (selectedWord) {
    return (
      <WordDetail
        word={selectedWord}
        onClose={() => setSelectedWord(null)}
        onUpdateNote={(note) => updateNote(selectedWord.word, note)}
        onDelete={() => deleteWord(selectedWord.word)}
      />
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-primary" />
            <h1 className="text-lg font-semibold text-foreground">单词本</h1>
            <Badge variant="secondary">{totalCount} 词</Badge>
          </div>
          <Button onClick={handleStartReview} disabled={totalCount === 0}>
            <Play className="w-4 h-4 mr-1" />
            开始复习
          </Button>
        </div>

        {/* Stats */}
        {stats && (
          <div className="flex gap-4 text-sm mb-4 text-foreground">
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-green-500" />
              <span>已掌握 {stats.mastered_count}</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-yellow-500" />
              <span>复习中 {stats.reviewing_count}</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-gray-500" />
              <span>待复习 {stats.pending_count}</span>
            </div>
            <span className="text-muted-foreground">
              今日复习 {stats.today_reviewed} 次
            </span>
          </div>
        )}

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="搜索单词..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      {/* Word List */}
      <div className="flex-1 overflow-y-auto p-4">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
          </div>
        ) : filteredWords.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
            <BookOpen className="w-12 h-12 mb-4 opacity-50" />
            <p>{searchQuery ? "没有找到匹配的单词" : "还没有收藏任何单词"}</p>
            <p className="text-sm mt-1">
              点击消息中的单词可以查词并收藏
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            <AnimatePresence>
              {filteredWords.map((word) => (
                <WordCard
                  key={word.word}
                  word={word}
                  onDelete={() => deleteWord(word.word)}
                  onUpdateNote={(note) => updateNote(word.word, note)}
                  onClick={() => setSelectedWord(word)}
                />
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>
    </div>
  );
}
