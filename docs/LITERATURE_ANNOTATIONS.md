# Литература: проверенные источники для технической части статьи

Составлено 03.11.2026. Все PDF скачаны из открытых источников (arXiv, ISCA Archive,
NIST, ITU, EBU, сайты авторов и лабораторий). Они лежат в `literature/pdf/`; папка
не хранится в Git, восстанавливается по ссылкам ниже и сверяется по SHA-256. Для
работы с базой автора файлы можно скопировать в `Thesis/Article base/`.

Перед записью в индекс каждый файл проверен: заголовок и авторы на первой странице
совпадают с записью. Числа ниже выписаны из текста PDF (pypdf), а не по памяти.
Первая скачанная копия Moreno 1998 оказалась другой статьёй того же сборника; она
удалена и заменена правильной.

## Индекс

| Ключ | Источник | Роль в статье | URL | SHA-256 (первые 16) |
|---|---|---|---|---|
| Rousso2024 | Rousso, Cohen, Keshet, Chodroff. *Tradition or Innovation: A Comparison of Modern ASR Methods for Forced Alignment*. Interspeech 2024 (arXiv 2406.19363) | Главный аналог: MFA против WhisperX и MMS на тех же TIMIT и Buckeye; числа для таблицы сравнения | https://arxiv.org/pdf/2406.19363 | fa29f90008ebc14f |
| Rastorgueva2023 | Rastorgueva, Lavrukhin, Ginsburg. *NeMo Forced Aligner and its application to word alignment for subtitle generation*. Interspeech 2023 (Show & Tell) | Ближайший аналог по задаче (пословные субтитры); сбои MFA на длинных файлах | https://www.isca-archive.org/interspeech_2023/rastorgueva23_interspeech.pdf | 7cd1795bd2feb844 |
| Stolcke2014 | Stolcke, Ryant, Mitra, Yuan, Wang, Liberman. *Highly Accurate Phonetic Segmentation Using Boundary Correction Models and System Fusion*. ICASSP 2014 | Прямой предшественник BRQE: статистическая коррекция границ поверх HMM | https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/icassp2014-phoneseg-v10-fixed.pdf | 09651dea6ee11a36 |
| Moreno1998 | Moreno, Joerg, Van Thong, Glickman. *A Recursive Algorithm for the Forced Alignment of Very Long Audio Segments*. ICSLP 1998 | Классика выравнивания длинных записей (RQ3) | https://www.isca-archive.org/icslp_1998/moreno98b_icslp.pdf | bb66daa071911ece |
| Kurzinger2020 | Kürzinger, Winkelbauer, Li, Watzel, Rigoll. *CTC-Segmentation of Large Corpora for German End-to-end Speech Recognition*. SPECOM 2020 (arXiv 2007.09127) | CTC-выравнивание длинного аудио, современный подход (RQ3) | https://arxiv.org/pdf/2007.09127 | 3c71864510debae2 |
| Zhu2022 | Zhu, Zhang, Jurgens. *Phone-to-audio alignment without text: A semi-supervised approach* (Charsiu). ICASSP 2022 (arXiv 2110.03876) | Нейросетевые выравниватели на wav2vec2 как альтернатива MFA | https://arxiv.org/pdf/2110.03876 | 67d085ad3edaa056 |
| Pitt2005 | Pitt, Johnson, Hume, Kiesling, Raymond. *The Buckeye corpus of conversational speech: labeling conventions and a test of transcriber reliability*. Speech Communication 45 (2005) 89–95 | Обязательная ссылка на корпус | https://u.osu.edu/lplab/files/2020/06/Buckeye.Corpus-5.pdf | bd02eed3f265d4b3 |
| Raymond2002 | Raymond, Pitt, Johnson, Hume, Makashay, Dautricourt, Hilts. *An analysis of transcription consistency in spontaneous speech from the Buckeye corpus*. ICSLP 2002 | Согласие разметчиков: шум эталона | https://www.isca-archive.org/icslp_2002/raymond02_icslp.pdf | 421f8b95603800e3 |
| Garofolo1993 | Garofolo, Lamel, Fisher, Fiscus, Pallett, Dahlgren. *DARPA TIMIT Acoustic-Phonetic Continuous Speech Corpus CD-ROM*. NISTIR 4930 (1993) | Обязательная ссылка на корпус (скан, текст не извлекается) | https://nvlpubs.nist.gov/nistpubs/Legacy/IR/nistir4930.pdf | ab6ee9f8f8aaa55f |
| ITU1998 | Recommendation ITU-R BT.1359-1 (11/1998). *Relative timing of sound and vision for broadcasting* | Пороги заметности и приемлемости рассинхрона | https://www.itu.int/dms_pubrec/itu-r/rec/bt/R-REC-BT.1359-1-199811-I!!PDF-E.pdf | 1e6f61373b6900d7 |
| EBU2007 | EBU Recommendation R37-2007. *The relative timing of the sound and vision components of a television signal* | Допуски синхронизации в вещании | https://tech.ebu.ch/files/live/sites/tech/files/shared/r/r037.pdf | 045d5619b9c14d91 |
| McAuliffe2026 | McAuliffe, Gunter, Wagner, Sonderegger. *Montreal Forced Aligner and the state of speech-to-text alignment in 2026*. Interspeech 2026, 347–356 | Актуальный ориентир точности MFA на TIMIT и Buckeye; как готовят данные для бенчмарка | https://www.isca-archive.org/interspeech_2026/mcauliffe26_interspeech.pdf | 3994e24c486449d9 |
| Mu2026 | Mu, Shi, Wang, Liu, Xu, Xie. *LLM-ForcedAligner: A Non-Autoregressive and Accurate LLM-Based Forced Aligner for Multilingual and Long-Form Speech*. ACL 2026, Long Papers, 25627–25638 | Сдвиг выравнивателей на склеенной длинной речи (RQ3); современный нейросетевой подход | https://aclanthology.org/2026.acl-long.1174.pdf | b18aa8d9b30bff96 |

Полные SHA-256 (имя файла → хэш):

```
EBU2007_R37.pdf                                  045d5619b9c14d9139ec7c9434c271c77602bae74aee8bd3c557656364024f93
Garofolo1993_TIMIT_NISTIR4930.pdf                ab6ee9f8f8aaa55f3c395a3efcb916e915c35fc48b4ff22c1ea6264034c8e1da
ITU1998_BT1359-1.pdf                             1e6f61373b6900d76dcc0be13af8d86055794876e325ff7bc630f44a0d775acc
Kurzinger2020_CTCSegmentation.pdf                3c71864510debae281c8f439ad384edbd78c13aa2f41bc9ad0e3969a215507f3
McAuliffe2026_Interspeech.pdf                    3994e24c486449d984bc36b8d37f35c46e9d1290923934840e747c13f6b06d33
Moreno1998_RecursiveLongAlignment.pdf            bb66daa071911ecec15318f13c483ff05dcb224ef8a9c579a082ea5e53c22139
Mu2026_ACL.pdf                                   b18aa8d9b30bff962f2c794de9eb20a4117ba23b1293529d798367fb73c83c9e
Pitt2005_BuckeyeCorpus.pdf                       bd02eed3f265d4b36831a3c9e3d9d88bac1322830792c3e010fd7b4f61aff272
Rastorgueva2023_NeMoForcedAligner.pdf            7cd1795bd2feb844f156021045384037c810d48fbf3a0db9f51870b06ece4067
Raymond2002_BuckeyeTranscriptionConsistency.pdf  421f8b95603800e3abb2fc3e399626ce99fc9e6611a06ff08225f66e24755286
Rousso2024_ForcedAlignmentComparison.pdf         fa29f90008ebc14f50a01cbd271669acaf2e7b2396c502e2ac73bde6dfb99401
Stolcke2014_BoundaryCorrection.pdf               09651dea6ee11a36d1383481a3f758984ea80092a2ee6e5fcc728a61ce7b7c3e
Zhu2022_Charsiu.pdf                              67d085ad3edaa056102e12a5cbd6eea0099308293e1eed74206c94801c03690b
```

**Не найдено в открытом доступе:** van Wassenhove, Grant, Poeppel (2007),
*Temporal window of integration in auditory-visual speech perception*,
Neuropsychologia, DOI 10.1016/j.neuropsychologia.2006.01.001. Это платный источник,
можно взять через библиотеку AITU. Без него статья обходится: пороги восприятия
рассинхрона дают ITU и EBU.

## Ключевые факты (проверено по тексту PDF)

**Rousso2024.**
- MFA превзошёл WhisperX и MMS на пословном выравнивании на TIMIT и Buckeye при всех
  порогах. Сравнение велось только по словам, которые ASR распознал верно.
- Табл. 1, TIMIT, доля границ при t ≤ 10 / 25 / 50 / 100 мс:
  - MFA — 41,6 / 72,8 / 89,4 / 97,4 %;
  - MMS — 18,6 / 43,5 / 75,7 / 94,7 %;
  - WhisperX — 22,4 / 52,7 / 82,4 / 94,2 %.
- Табл. 2, Buckeye, без порога 500 мс:
  - MFA — 39,8 / 69,9 / 84,9 / 91,8 %;
  - MMS — 25,0 / 52,7 / 75,0 / 87,9 %;
  - WhisperX — 18,8 / 43,1 / 67,4 / 77,4 %.
- Табл. 3, слова на TIMIT, среднее / медиана в мс:
  - MFA — 21,9 / 12,5;
  - MMS — 68,5 / 29,3;
  - WhisperX — 34,3 / 23,5.

  На Buckeye без порога средние огромны из-за выбросов (MFA — 976,5 мс), поэтому для
  сравнения брать медианы и доли.
- **Значение для нас:** независимое подтверждение нашего порядка «MFA точнее
  CTC-подходов». Метрики похожи, но не тождественны нашим: у них доля границ,
  у нас MAE по началу и концу. Выборки клипов тоже разные, поэтому сопоставление
  только качественное.

**Rastorgueva2023.**
- NFA основан на CTC-моделях NeMo и генерирует субтитры с подсветкой слов.
- Оценка на AMI (длинные записи совещаний), совпадение слова засчитывается в пределах
  200 мс, как в статье о WhisperX. С эталонным текстом: NFA — precision/recall
  98,35 %, CTC-segmentation — 98,17 %, Gentle — 94,47 / 78,72 %.
- MFA выровнял только 5 из 16 аудиофайлов. Это независимое свидетельство того, что
  MFA плохо переносит длинные записи без нарезки; напрямую связано с нашими S1/S1b.
- Короткая демонстрационная статья на 2 страницы. Порог 200 мс гораздо грубее
  наших 20 мс.

**Stolcke2014.**
- Коррекция границ статистическими моделями (фонетический контекст, длительность)
  поверх HMM-выравнивания плюс слияние нескольких акустических фронтендов.
- На TIMIT ошибки сегментации сократились почти вдвое: точность границ при допуске
  20 мс выросла с 93,9 до 96,8 %.
- **Значение для нас:** идея BRQE (коррекция границ поверх HMM) не нова. Наш вклад
  иной:
  - лёгкая модель на мел-окне;
  - **оценка надёжности** каждой границы;
  - честная проверка на отложенных дикторах разговорной речи и перенос на другой
    корпус.

  Писать о BRQE именно так, без претензии на первенство идеи коррекции.

**Moreno1998.**
- Выравнивание очень длинного аудио (часто больше часа) рекурсивным распознаванием с
  постепенно сужающимся словарём и языковой моделью.
- Устойчив к шуму и к пропускам в тексте. Эксперимент на 3 часах теле- и
  радиопередач.

**Kurzinger2020.**
- CTC-segmentation: выравнивание текста с длинным несегментированным аудио с помощью
  CTC-модели. Применено для сбора более 1700 ч немецкой речи.

**Zhu2022 (Charsiu).**
- Модели на wav2vec2 для выравнивания по тексту и без текста. Результаты близки к
  существующим инструментам принудительного выравнивания.

**Pitt2005.**
- Корпус на 307 000 слов, 40 говорящих из центрального Огайо.
- Описаны протокол фонемной разметки и проверка согласия: четыре минутных фрагмента
  по 220 слов, каждый размечен четырьмя разметчиками.

**Raymond2002.**
- Точное совпадение метки фонемы между парами разметчиков — 76 %.
- Согласие сегментации — 75 %, но в пределах **20 % длины пары фонем**, а не в мс.
- Короткие и редуцированные фонемы согласуются хуже.
- **Поправка к старым документам:** в `docs/RESEARCH_AND_LITERATURE_STRATEGY.md` этой
  статье приписан «шум разметки 10–16 мс». В её тексте такого числа нет. Его нельзя
  цитировать со ссылкой на Raymond2002, пока не найден настоящий источник.

**ITU1998 (BT.1359-1).**
- Пороги заметности рассинхрона примерно от +45 мс до −125 мс, пороги приемлемости —
  от +90 мс до −185 мс (плюс — звук раньше изображения).
- Тракт от финального источника программы до входа передатчика: допуск от +22,5 мс
  до −30 мс.
- **Поправка:** в старой стратегии записано «≤ 50 мс». Точные значения — выше.

**EBU2007 (R37).**
- Сквозные пределы: звук раньше изображения ≤ 40 мс, позже ≤ 60 мс.
- Точность на каждом этапе: от 5 мс раньше до 15 мс позже.

**McAuliffe2026 (добавлено 04.11.2026).** Опубликовано в Interspeech 2026. Числа ниже сверены
с PDF из ISCA Archive и совпали с препринтом.
- Табл. 4, слова, среднее в мс и доля границ при t ≤ 10 / 25 / 50 / 100 мс:
  - MFA ARPA 3.0, TIMIT — 19,93; 44,99 / 66,50 / 91,61 / 98,38 %;
  - MFA ARPA 3.0, Buckeye — 21,75; 48,76 / 70,16 / 91,35 / 97,29 %.
- Средняя ошибка на тех же корпусах: WhisperX — 110,04 и 110,90 мс, NeMo — 78,24 и
  88,62 мс (TIMIT и Buckeye).
- Фонемы, MFA ARPA 3.0: 12,11 мс на TIMIT и 13,87 мс на Buckeye. MFA 1.0: 16,4 и 17,6 мс.
- Подготовка данных: спонтанная речь нарезана на фразы, разделённые паузой 300 мс, с запасом
  тишины 200 мс; фразы до трёх слов и фразы с неизвестными, оборванными и вырезанными словами
  отброшены.
- В извлечённом тексте нет числа невыровненных фраз (поиск по «failed», «failure», «could
  not», «unable to», «not aligned»). Режим длинных записей не оценивался.
- Адаптация модели к корпусу внутри того же языка почти ничего не меняет. Это адаптация
  модели, а не адаптация к диктору, которая есть у нас.
- MFA 3.0 умеет сегментировать длинные файлы, в том числе итеративно по тексту.
- **Значение для нас:** независимое подтверждение порядка величин (наши A2: 20,3 мс TIMIT,
  19,6 мс Buckeye) и превосходства MFA над WhisperX и NeMo. Сравнение только качественное:
  другие выборки, другая подготовка Buckeye, версия модели не обязательно та же. Такая
  подготовка не входит в режим, где у нас появляются провалы, поэтому о них статья данных не
  даёт.

**Mu2026 (добавлено 04.11.2026).** Опубликовано в ACL 2026. Числа ниже сверены с PDF из ACL
Anthology и совпали с препринтом.
- Предлагает нейросетевой выравниватель на речевой LLM. Метрика — накопленный средний сдвиг
  (AAS), а не MAE границ.
- Английский, AAS в мс, обычная речь: NFA — 107,5, WhisperX — 92,1, LLM-ForcedAligner — 37,5.
  Склейки до 300 с: 226,7 / 227,2 / 58,6.
- **Главная оговорка:** эталон этих таблиц — псевдометки MFA. Ручная разметка есть только
  для внутреннего китайского набора (ограничение названо самими авторами). Поэтому статья
  не оценивает точность MFA и не сообщает о его провалах.
- Авторы называют MFA самым точным из существующих методов и потому берут его как учителя.
- **Значение для нас:** склейка коротких записей в длинные — принятый приём (как наш S1).
  Нейросетевые выравниватели страдают на длинной речи иначе: дают результат, но со сдвигом.
  Числа с нашими несопоставимы (метрика, язык, эталон).

## Как использовать в статье

- **Пороги.** Порог Acc@20ms обосновывать опорой на литературу о выравнивании
  (Stolcke2014, Rousso2024 используют 20 мс). Пороги вещания (ITU/EBU: заметность
  от +45 / −125 мс, сквозной допуск 40 / 60 мс) показывают, что типичные ошибки
  MFA в десятки мс ниже порогов заметности рассинхрона, а метки Whisper (около
  150 мс на TIMIT, наш B0) — выше. Это аргумент практической значимости. Пороги
  вещания относятся к рассинхрону звука и изображения, а не к субтитрам; в тексте
  это оговорить.
- **Шум эталона:** Raymond2002 и Pitt2005 (согласие разметчиков) — без перевода в мс.
- **Правило журнала о давности.** Источники 1993–2014 (корпуса, стандарты, классика)
  допустимы как первоисточники; их доля должна быть малой. Основную массу ссылок
  набирать из 2020–2026.
