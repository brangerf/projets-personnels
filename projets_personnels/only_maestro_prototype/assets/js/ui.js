function normalizeUnicodeMath(content) {
    const unicodeToLatex = {
        '²': '^2',
        '³': '^3',
        '¹': '^1',
        '⁴': '^4',
        '⁵': '^5',
        '⁶': '^6',
        '⁷': '^7',
        '⁸': '^8',
        '⁹': '^9',
        '⁰': '^0',
        '√': '\\sqrt',
        '×': '\\times',
        '÷': '\\div',
        '±': '\\pm',
        '≈': '\\approx',
        '≠': '\\neq',
        '≤': '\\leq',
        '≥': '\\geq',
        '∞': '\\infty',
        'α': '\\alpha',
        'β': '\\beta',
        'γ': '\\gamma',
        'δ': '\\delta',
        'θ': '\\theta',
        'π': '\\pi',
        'Δ': '\\Delta',
        'Σ': '\\Sigma',
        'Π': '\\Pi',
        'Ω': '\\Omega'
    };
    
    let result = content;
    for (const [unicode, latex] of Object.entries(unicodeToLatex)) {
        result = result.split(unicode).join(latex);
    }
    
    return result;
}

function fixSqrtNotation(content) {
    content = content.replace(/\\sqrt\s*(\d+)/g, '\\sqrt{$1}');
    
    content = content.replace(/\\sqrt\s*\(([^)]+)\)/g, '\\sqrt{$1}');
    
    return content;
}

function autoWrapLatex(content) {
    const latexCommands = [
        '\\\\sqrt', '\\\\frac', '\\\\text', '\\\\times', '\\\\div', '\\\\pm', '\\\\mp',
        '\\\\leq', '\\\\geq', '\\\\neq', '\\\\approx', '\\\\equiv', '\\\\sim',
        '\\\\sum', '\\\\prod', '\\\\int', '\\\\lim', '\\\\infty',
        '\\\\alpha', '\\\\beta', '\\\\gamma', '\\\\delta', '\\\\theta', '\\\\pi',
        '\\\\sin', '\\\\cos', '\\\\tan', '\\\\log', '\\\\ln',
        '\\\\left', '\\\\right', '\\\\circ', '\\\\Delta', '\\\\Sigma', '\\\\Pi', '\\\\Omega'
    ].join('|');
    
    const mathPatterns = [
        `(${latexCommands})(?:\\s*\\{[^}]+\\})+`,
        `\\\\sqrt\\s*\\d+`,
        '[a-zA-Z][a-zA-Z0-9]*[\\^_](?:\\{[^}]+\\}|\\d+|[a-zA-Z])',
        '\\^(?:\\{[^}]+\\}|\\d+)',
        '_(?:\\{[^}]+\\}|[a-zA-Z]|\\d+)',
        '\\\\frac\\s*\\{[^}]+\\}\\s*\\{[^}]+\\}',
        `(?:${latexCommands})(?![a-zA-Z])`,
        '\\^\\\\circ'
    ];
    
    const combinedPattern = new RegExp(`(${mathPatterns.join('|')})`, 'g');
    
    function isAlreadyInLatex(text, index) {
        let dollarCount = 0;
        let lastDollarPos = -1;
        for (let i = index - 1; i >= 0; i--) {
            if (text[i] === '$') {
                dollarCount++;
                lastDollarPos = i;
                if (i > 0 && text[i-1] === '$') {
                    return true;
                }
            } else if (text[i] === '\n' || text[i] === '\r') {
                break;
            }
        }
        return dollarCount % 2 === 1;
    }
    
    const lines = content.split('\n');
    const processedLines = lines.map(line => {
        if (line.includes('$$') || line.match(/^\s*```/) || line.match(/^\s{4,}/)) {
            return line;
        }
        
        let processedLine = line;
        let offset = 0;
        const matches = [...line.matchAll(combinedPattern)];
        
        for (const match of matches) {
            const matchStart = match.index + offset;
            const matchText = match[0];
            
            if (!isAlreadyInLatex(processedLine, matchStart)) {
                const before = processedLine.substring(Math.max(0, matchStart - 10), matchStart);
                if (!before.includes('http') && !before.includes('](') && !before.includes('$')) {
                    const beforeText = processedLine.substring(0, matchStart);
                    const afterText = processedLine.substring(matchStart + matchText.length);
                    processedLine = beforeText + '$' + matchText + '$' + afterText;
                    offset += 2;
                }
            }
        }
        
        return processedLine;
    });
    
    return processedLines.join('\n');
}

function mergeAdjacentMath(content) {
    const operators = [
        '\\+', '-', '\\*', '/', '=', 
        '≈', '≠', '≤', '≥', 
        '×', '÷', '±',
        '\\\\approx', '\\\\neq', '\\\\leq', '\\\\geq',
        '\\\\times', '\\\\div', '\\\\pm',
        '<', '>'
    ].join('|');
    
    const pattern = new RegExp(`\\$([^\\$\\n]+?)\\$\\s*(${operators})\\s*\\$([^\\$\\n]+?)\\$`, 'g');
    
    let result = content;
    let prevResult;
    let iterations = 0;
    const maxIterations = 20;
    do {
        prevResult = result;
        result = result.replace(pattern, (match, left, operator, right) => {
            return `$${left} ${operator} ${right}$`;
        });
        iterations++;
    } while (result !== prevResult && iterations < maxIterations);
    
    return result;
}

function cleanupLatexDelimiters(content) {
    content = content.replace(/\$\s*\$/g, '');
    
    content = content.replace(/\$\$([^\$]+?)\$\$/g, (match, inner) => {
        if (!inner.includes('\n') && inner.length < 100) {
            return `$${inner}$`;
        }
        return match;
    });
    
    content = content.replace(/\$([^\$]+)\$/g, (match, formula) => {
        const cleaned = formula.replace(/\s+/g, ' ').trim();
        return `$${cleaned}$`;
    });
    
    return content;
}

function processFinalContent(element, content) {
    const contentWrapper = document.createElement('div');
    contentWrapper.className = 'message-content';

    try {
        console.log('🔍 Traitement du contenu, longueur:', content.length);
        
        if (typeof katex === 'undefined') {
            console.error('❌ KaTeX n\'est pas chargé !');
            element.textContent = content;
            return;
        }
        
        let processedContent = content;
        
        processedContent = normalizeUnicodeMath(processedContent);
        
        processedContent = fixSqrtNotation(processedContent);
        
        processedContent = autoWrapLatex(processedContent);
        
        processedContent = mergeAdjacentMath(processedContent);
        
        processedContent = cleanupLatexDelimiters(processedContent);
        
        console.log('🔍 Contenu après pré-traitement:', processedContent.substring(0, 200));
        
        const latexFormulas = [];
        let formulaIndex = 0;
        
        processedContent = processedContent.replace(/\$\$([\s\S]*?)\$\$/g, (match, latex) => {
            const id = `LATEX_DISPLAY_${formulaIndex}`;
            latexFormulas.push({
                id: id,
                latex: latex.trim(),
                displayMode: true
            });
            formulaIndex++;
            console.log(`📐 Display: ${latex.trim().substring(0, 50)}`);
            return `<span class="latex-placeholder" data-formula-id="${id}"></span>`;
        });
        
        processedContent = processedContent.replace(/\$([^\$\n]+?)\$/g, (match, latex) => {
            const id = `LATEX_INLINE_${formulaIndex}`;
            latexFormulas.push({
                id: id,
                latex: latex.trim(),
                displayMode: false
            });
            formulaIndex++;
            console.log(`📐 Inline: ${latex.trim().substring(0, 50)}`);
            return `<span class="latex-placeholder" data-formula-id="${id}"></span>`;
        });
        
        console.log(`📐 ${latexFormulas.length} formule(s) LaTeX extraite(s)`);
        
        contentWrapper.innerHTML = marked.parse(processedContent, { gfm: true, breaks: true });
        
        if (latexFormulas.length > 0) {
            const placeholders = contentWrapper.querySelectorAll('.latex-placeholder');
            console.log(`🔄 Remplacement de ${placeholders.length} placeholder(s)`);
            
            placeholders.forEach((placeholder, idx) => {
                const formulaId = placeholder.getAttribute('data-formula-id');
                const formula = latexFormulas.find(f => f.id === formulaId);
                
                if (formula) {
                    try {
                        const span = document.createElement('span');
                        if (formula.displayMode) {
                            span.className = 'katex-display-wrapper';
                        }
                        
                        katex.render(formula.latex, span, {
                            displayMode: formula.displayMode,
                            throwOnError: false,
                            trust: true,
                            strict: false,
                            output: 'html'
                        });
                        
                        placeholder.replaceWith(span);
                        console.log(`✅ ${idx+1}/${placeholders.length} Formule rendue: ${formula.latex.substring(0, 30)}...`);
                    } catch (e) {
                        console.error('❌ Erreur rendu KaTeX:', e, 'Formule:', formula.latex);
                        const errorSpan = document.createElement('span');
                        errorSpan.style.color = '#ff6b6b';
                        errorSpan.textContent = formula.displayMode ? `$$${formula.latex}$$` : `$${formula.latex}$`;
                        placeholder.replaceWith(errorSpan);
                    }
                } else {
                    console.warn('⚠️ Formule non trouvée pour:', formulaId);
                }
            });
        }

        contentWrapper.querySelectorAll('pre').forEach(pre => {
            const code = pre.querySelector('code');
            if (!code) return;

            const buttonContainer = document.createElement('div');
            buttonContainer.style.position = 'absolute';
            buttonContainer.style.top = '8px';
            buttonContainer.style.right = '8px';
            pre.style.position = 'relative';
            pre.appendChild(buttonContainer);

            const copyButton = document.createElement('button');
            copyButton.className = 'copy-code-button';
            copyButton.innerHTML = '<i class="fa-regular fa-copy"></i> Copier';
            copyButton.style.position = 'static';
            buttonContainer.appendChild(copyButton);

            copyButton.addEventListener('click', (e) => {
                e.stopPropagation();
                navigator.clipboard.writeText(code.textContent).then(() => {
                    copyButton.innerHTML = '<i class="fa-solid fa-check"></i> Copié !';
                    setTimeout(() => { copyButton.innerHTML = '<i class="fa-regular fa-copy"></i> Copier'; }, 2000);
                });
            });
        });
        
        contentWrapper.querySelectorAll('pre code').forEach(block => {
            if (typeof hljs !== 'undefined') hljs.highlightElement(block);
        });

        element.innerHTML = '';
        element.appendChild(contentWrapper);
        console.log('✅ Traitement terminé avec succès');

    } catch (e) {
        console.error('❌ Erreur lors du traitement du contenu final:', e);
        console.error('Stack trace:', e.stack);
        element.textContent = content;
    }
}