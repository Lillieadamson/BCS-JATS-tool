<?xml version="1.0"?>
<!-- ============================================================= -->
<!--  MODULE:    HTML Preview of NISO JATS Publishing 1.0 XML      -->
<!--  DATE:      May-June 2012                                     -->
<!--                                                               -->
<!-- ============================================================= -->

<!-- ============================================================= -->
<!--  SYSTEM:    NCBI Archiving and Interchange Journal Articles   -->
<!--                                                               -->
<!--  PURPOSE:   Provide an HTML preview of a journal article,     -->
<!--             in a form suitable for reading.                   -->
<!--                                                               -->
<!--  PROCESSOR DEPENDENCIES:                                      -->
<!--             None: standard XSLT 1.0                           -->
<!--             Tested using Saxon 6.5, Tranformiix (Firefox),    -->
<!--               Saxon 9.4.0.3                                   -->
<!--                                                               -->
<!--  COMPONENTS REQUIRED:                                         -->
<!--             1) This stylesheet                                -->
<!--             2) CSS styles defined in jats-preview.css         -->
<!--                (to be placed with the results)                -->
<!--                                                               -->
<!--  INPUT:     An XML document valid to (any of) the             -->
<!--             NISO JATS 1.0, NLM/NCBI Journal Publishing 3.0,   -->
<!--             or NLM/NCBI Journal Publishing 2.3 DTDs.          -->
<!--             (May also work with older variants,               -->
<!--             and note further assumptions and limitations      -->
<!--             below.)                                           -->
<!--                                                               -->
<!--  OUTPUT:    HTML (XHTML if a postprocessor is used)           -->
<!--                                                               -->
<!--  CREATED FOR:                                                 -->
<!--             Digital Archive of Journal Articles               -->
<!--             National Center for Biotechnology Information (NCBI)     -->
<!--             National Library of Medicine (NLM)                -->
<!--                                                               -->
<!--  CREATED BY:                                                  -->
<!--             Wendell Piez (based on HTML design by             -->
<!--             Kate Hamilton and Debbie Lapeyre, 2004),          -->
<!--             Mulberry Technologies, Inc.                       -->
<!--                                                               -->
<!-- ============================================================= -->

<!-- ============================================================= -->
<!-- 
  This work is in the public domain and may be reproduced, published or 
  otherwise used without the permission of the National Library of Medicine (NLM).
  
  We request only that the NLM is cited as the source of the work.
  
  Although all reasonable efforts have been taken to ensure the accuracy and 
  reliability of the software and data, the NLM and the U.S. Government  do 
  not and cannot warrant the performance or results that may be obtained  by
  using this software or data. The NLM and the U.S. Government disclaim all 
  warranties, express or implied, including warranties of performance, 
  merchantability or fitness for any particular purpose.
-->
<!-- ============================================================= -->

<!-- Change history                                                -->

<!-- From jpub3-html.xsl v3.0 to jats-html.xsl v1.0:
  
Calls to 'normalize-space($node)' where $node is not a string are
expressed as 'normalize-space(string($node)) in order to provide
type safety in some XSLT 2.0 processors.

Support for certain elements in NLM Blue v2.3 is added to provide
backward compatibility:
  floats-wrap (same as floats-group)
  chem-struct-wrapper (same as chem-struct-wrap)
  custom-meta-wrap (same as custom-meta-group)
  floats-wrap (same as floats-group)
  gloss-group (same as glossary)
  citation
  contract-num
  contract-sponsor
  grant-num
  grant-sponsor

Support is added for looser structures for title-group elements
in 2.3 (title, trans-title, trans-subtitle etc.) Same for 2.3
tagging of permissions info (copyright-statement, copyright-year,
license) and funding/contract info (contract-num, contract-sponsor,
grant-num, grant-sponsor).

Elements newly permitted in JATS journal-meta
(contrib-group, aff, aff-alternatives) are supported.

New elements in NISO JATS v1.0 are supported:
  aff-alternatives
  citation-alternatives
  collab-alternatives
  trans-title-group (with @xml:lang)
  contrib-id
  count>
  issn-l
  nested-kwd

Added support for @pub-id-type='arXiv'

Named anchor logic extended to support "alternatives" wrappers
for aff, contrib, citation etc.

Footer text is emended, with name of transformation (stylesheet
or pipeline) parameterized.

-->
<xsl:stylesheet version="1.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:xlink="http://www.w3.org/1999/xlink"
  xmlns:mml="http://www.w3.org/1998/Math/MathML"
  exclude-result-prefixes="xlink mml">


  <!--<xsl:output method="xml" indent="no" encoding="UTF-8"
    doctype-public="-//W3C//DTD XHTML 1.0 Transitional//EN"
    doctype-system="http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"/>-->
  
  
  <xsl:output method="html" indent="yes" encoding="UTF-8"
    doctype-system="about:legacy-compat"/>

  <xsl:strip-space elements="*"/>

  <!-- Space is preserved in all elements allowing #PCDATA -->
  <xsl:preserve-space
    elements="abbrev abbrev-journal-title access-date addr-line
              aff alt-text alt-title article-id article-title
              attrib award-id bold chapter-title chem-struct
              collab comment compound-kwd-part compound-subject-part
              conf-acronym conf-date conf-loc conf-name conf-num
              conf-sponsor conf-theme contrib-id copyright-holder
              copyright-statement copyright-year corresp country
              date-in-citation day def-head degrees disp-formula
              edition elocation-id email etal ext-link fax fpage
              funding-source funding-statement given-names glyph-data
              gov inline-formula inline-supplementary-material
              institution isbn issn-l issn issue issue-id issue-part
              issue-sponsor issue-title italic journal-id
              journal-subtitle journal-title kwd label license-p
              long-desc lpage meta-name meta-value mixed-citation
              monospace month named-content object-id on-behalf-of
              overline p page-range part-title patent person-group
              phone prefix preformat price principal-award-recipient
              principal-investigator product pub-id publisher-loc
              publisher-name related-article related-object role
              roman sans-serif sc season self-uri series series-text
              series-title sig sig-block size source speaker std
              strike string-name styled-content std-organization
              sub subject subtitle suffix sup supplement surname
              target td term term-head tex-math textual-form th
              time-stamp title trans-source trans-subtitle trans-title
              underline uri verse-line volume volume-id volume-series
              xref year

              mml:annotation mml:ci mml:cn mml:csymbol mml:mi mml:mn 
              mml:mo mml:ms mml:mtext"/>

  
  <xsl:param name="transform" select="'jats-html.xsl'"/>

  <xsl:param name="css" select="'style.css'"/>

  <!-- masthead image, uploaded to OJS as a dependent file of the galley -->
  <xsl:param name="logo" select="'logo.png'"/>
  
  <xsl:param name="report-warnings" select="'no'"/>
  
  <xsl:variable name="verbose" select="$report-warnings='yes'"/>
  
  <!-- Keys -->

  <!-- To reduce dependency on a DTD for processing, we declare
       a key to use instead of the id() function. -->
  <xsl:key name="element-by-id" match="*[@id]" use="@id"/>

  <!-- Enabling retrieval of cross-references to objects -->
  <xsl:key name="xref-by-rid" match="xref" use="@rid"/>
  
  <!-- ============================================================= -->
  <!--  ROOT TEMPLATE - HANDLES HTML FRAMEWORK                       -->
  <!-- ============================================================= -->

  <xsl:template match="/">
    <html>
      <xsl:attribute name="lang">
        <xsl:choose>
          <xsl:when test="normalize-space(/article/@xml:lang)">
            <xsl:value-of select="/article/@xml:lang"/>
          </xsl:when>
          <xsl:otherwise>en</xsl:otherwise>
        </xsl:choose>
      </xsl:attribute>
      <!-- HTML header -->
      <xsl:call-template name="make-html-header"/>
      <body>
        <!-- Masthead. The file is uploaded to OJS as a dependent file of
             the HTML galley, named exactly "logo.png", the same way
             style.css is. A relative src keeps the galley self-contained:
             it also resolves when the HTML is opened straight off disk or
             deposited somewhere other than OJS. -->
        <div class="masthead">
          <img class="logo" src="{$logo}" alt="BC Studies"/>
        </div>
        <xsl:apply-templates/>
        <xsl:call-template name="galley-script"/>
      </body>
    </html>
  </xsl:template>


  <xsl:template name="make-html-header">
    <head>
      <!-- NB: with xsl:output method="html" the processor emits its own
           <meta http-equiv="Content-Type"> charset declaration. Do not add a
           second <meta charset> here - two charset declarations are invalid. -->
      <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
      <title>
        <xsl:variable name="authors">
          <xsl:call-template name="author-string"/>
        </xsl:variable>
        <xsl:value-of select="normalize-space(string($authors))"/>
        <xsl:if test="normalize-space(string($authors))">: </xsl:if>
        <xsl:value-of
          select="/article/front/article-meta/title-group/article-title[1]"/>
      </title>
      <xsl:call-template name="scholarly-meta"/>
      <!-- Noto Sans sets the whole galley; Noto Sans Canadian Aboriginal
           carries the syllabics. style.css @imports these too, so the page
           is still correct without them - the preconnect and link are here
           only so the fonts start downloading in parallel with the
           stylesheet rather than after it. -->
      <link rel="preconnect" href="https://fonts.googleapis.com"/>
      <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="crossorigin"/>
      <link rel="stylesheet" type="text/css"
        href="https://fonts.googleapis.com/css2?family=Noto+Sans:ital,wght@0,400;0,700;1,400;1,700&amp;family=Noto+Sans+Canadian+Aboriginal:wght@400;700&amp;display=swap"/>
      <link rel="stylesheet" type="text/css" href="{$css}"/>
    </head>
  </xsl:template>


  <!-- =============================================================== -->
  <!--  Google Scholar / indexing metadata (citation_* tags).          -->
  <!--  Harmless inside OJS, valuable when the galley is deposited     -->
  <!--  with ProQuest or harvested standalone.                         -->
  <!-- =============================================================== -->

  <xsl:template name="scholarly-meta">
    <xsl:for-each select="/article/front/article-meta">
      <meta name="citation_title"
        content="{normalize-space(string(title-group/article-title[1]))}"/>
      <xsl:for-each select="contrib-group[not(@content-type)]/contrib[not(@contrib-type) or @contrib-type='author']">
        <xsl:choose>
          <xsl:when test="name/surname">
            <meta name="citation_author"
              content="{normalize-space(concat(name/surname, ', ', name/given-names))}"/>
          </xsl:when>
          <xsl:when test="collab">
            <meta name="citation_author"
              content="{normalize-space(string(collab))}"/>
          </xsl:when>
        </xsl:choose>
      </xsl:for-each>
      <xsl:if test="normalize-space(string(/article/front/journal-meta//journal-title[1]))">
        <meta name="citation_journal_title"
          content="{normalize-space(string(/article/front/journal-meta//journal-title[1]))}"/>
      </xsl:if>
      <xsl:for-each select="/article/front/journal-meta/issn">
        <meta name="citation_issn" content="{normalize-space(string(.))}"/>
      </xsl:for-each>
      <xsl:if test="normalize-space(string(/article/front/journal-meta/publisher/publisher-name))">
        <meta name="citation_publisher"
          content="{normalize-space(string(/article/front/journal-meta/publisher/publisher-name))}"/>
      </xsl:if>
      <xsl:if test="normalize-space(string(volume))">
        <meta name="citation_volume" content="{normalize-space(string(volume))}"/>
      </xsl:if>
      <xsl:if test="normalize-space(string(issue))">
        <meta name="citation_issue" content="{normalize-space(string(issue))}"/>
      </xsl:if>
      <xsl:if test="normalize-space(string(fpage))">
        <meta name="citation_firstpage" content="{normalize-space(string(fpage))}"/>
      </xsl:if>
      <xsl:if test="normalize-space(string(lpage))">
        <meta name="citation_lastpage" content="{normalize-space(string(lpage))}"/>
      </xsl:if>
      <xsl:if test="article-id[@pub-id-type='doi']">
        <meta name="citation_doi"
          content="{normalize-space(string(article-id[@pub-id-type='doi'][1]))}"/>
      </xsl:if>
      <xsl:for-each select="(pub-date[@pub-type='epub'] | pub-date[@date-type='pub'] | pub-date)[1]">
        <meta name="citation_publication_date">
          <xsl:attribute name="content">
            <xsl:value-of select="year"/>
            <xsl:if test="month">
              <xsl:text>/</xsl:text><xsl:value-of select="month"/>
            </xsl:if>
            <xsl:if test="month and day">
              <xsl:text>/</xsl:text><xsl:value-of select="day"/>
            </xsl:if>
          </xsl:attribute>
        </meta>
      </xsl:for-each>
      <xsl:if test="abstract">
        <meta name="description"
          content="{normalize-space(string(abstract[1]))}"/>
      </xsl:if>
    </xsl:for-each>
  </xsl:template>


<!-- ============================================================= -->
<!--  TOP LEVEL                                                    -->
<!-- ============================================================= -->

  <!--
      content model for article:
         (front,body?,back?,floats-group?,(sub-article*|response*))
      
      content model for sub-article:
         ((front|front-stub),body?,back?,floats-group?,
          (sub-article*|response*))
      
      content model for response:
         ((front|front-stub),body?,back?,floats-group?) -->
  
  <xsl:template match="article">
    <xsl:call-template name="make-article"/>
  </xsl:template>

  <xsl:template match="sub-article | response">
    <hr class="part-rule"/>
    <xsl:call-template name="make-article"/>
  </xsl:template>


<!-- ============================================================= -->
<!--  "make-article" for the document architecture                 -->
<!-- ============================================================= -->
  
  <xsl:template name="make-article">
    <!-- Generates a series of (flattened) divs for contents of any
         article, sub-article or response -->
    
    <!-- variable to be used in div id's to keep them unique -->
    <xsl:variable name="this-article">
      <xsl:apply-templates select="." mode="id"/>
    </xsl:variable>
    
    
    <!-- ========================================== -->
    <!-- NEW: THIS GRID WRAPPER CREATES THE SPLIT   -->
    <!-- ========================================== -->
<div class="journal-layout-wrapper" id="{$this-article}-top">

      <!-- Scoped once here so nothing below has to reach for "//" , which
           would pick up <issue>/<fpage>/<source> out of the reference list
           (or out of the parent article, inside a sub-article). -->
      <xsl:variable name="meta" select="front/article-meta | front-stub"/>
      <xsl:variable name="doi"
        select="$meta/article-id[@pub-id-type='doi'][1]"/>
      <xsl:variable name="reflist"
        select="(back//ref-list[not(ancestor::sec)] | body/ref-list)[1]"/>
      <!-- archival profile parks the notes in back/fn-group; lens puts them in
           a body sec, which the sec loop below already picks up -->
      <xsl:variable name="notes" select="(back/fn-group)[1]"/>
      <xsl:variable name="ack" select="(back/ack)[1]"/>
      <xsl:variable name="funding" select="$meta/funding-group[funding-statement][1]"/>
      <xsl:variable name="ethics" select="(back/notes[@notes-type='ethics-statement'])[1]"/>
      <xsl:variable name="has-abstract" select="$meta/abstract | $meta/trans-abstract"/>

      <!-- ========================================== -->
      <!-- MAIN LEFT-SIDE CONTENT HOLDER              -->
      <!-- ========================================== -->
      <main class="journal-main-content">

        <div id="{$this-article}-front" class="front">
          <xsl:apply-templates select="front | front-stub"/>
        </div>

        <xsl:for-each select="body">
          <div id="{$this-article}-body" class="body">
            <xsl:apply-templates/>
          </div>
        </xsl:for-each>

        <xsl:if test="back | $loose-footnotes | $funding">
          <div id="{$this-article}-back" class="back">
            <xsl:call-template name="make-back"/>
          </div>
        </xsl:if>

        <xsl:for-each select="floats-group | floats-wrap">
          <div id="{$this-article}-floats" class="back">
            <xsl:call-template name="main-title">
              <xsl:with-param name="contents">
                <span class="generated">Floating objects</span>
              </xsl:with-param>
            </xsl:call-template>
            <xsl:apply-templates/>
          </div>
        </xsl:for-each>

      </main>

      <!-- ========================================== -->
      <!-- STICKY RIGHT-SIDE PANEL: cite + outline    -->
      <!-- ========================================== -->
      <nav class="journal-sidebar" aria-label="Article information and outline">

        <!-- PDF / Share / Rights and permissions -->
        <xsl:call-template name="sidebar-actions"/>

        <!-- How to cite: Chicago, MLA and APA -->
        <xsl:call-template name="sidebar-cite"/>

        <!-- Article outline -->
        <div class="sidebar-navigation">
          <xsl:if test="$has-abstract or body/sec[normalize-space(string(title))]
                        or $notes or $reflist or $ack or $funding or $ethics">
          <h2 class="sidebar-heading">Outline</h2>
          <ul>
            <xsl:if test="$has-abstract">
              <li><a href="#abstract-sec" class="nav-link">Abstract</a></li>
            </xsl:if>
            <!-- Titled top-level body sections only: an untitled <sec> would
                 produce a link with no accessible name. -->
            <xsl:for-each select="body/sec[normalize-space(string(title))]">
              <xsl:variable name="sec-id">
                <xsl:apply-templates select="." mode="id"/>
              </xsl:variable>
              <li>
                <a href="#{$sec-id}" class="nav-link">
                  <xsl:value-of select="normalize-space(string(title))"/>
                </a>
              </li>
            </xsl:for-each>
            <xsl:if test="$ack">
              <xsl:variable name="ack-id">
                <xsl:apply-templates select="$ack" mode="id"/>
              </xsl:variable>
              <li>
                <a href="#{$ack-id}" class="nav-link">
                  <xsl:choose>
                    <xsl:when test="normalize-space(string($ack/title))">
                      <xsl:value-of select="normalize-space(string($ack/title))"/>
                    </xsl:when>
                    <xsl:otherwise>Acknowledgements</xsl:otherwise>
                  </xsl:choose>
                </a>
              </li>
            </xsl:if>
            <xsl:if test="$funding">
              <xsl:variable name="funding-id">
                <xsl:apply-templates select="$funding" mode="id"/>
              </xsl:variable>
              <li><a href="#{$funding-id}" class="nav-link">Funding</a></li>
            </xsl:if>
            <xsl:if test="$ethics">
              <xsl:variable name="ethics-id">
                <xsl:apply-templates select="$ethics" mode="id"/>
              </xsl:variable>
              <li>
                <a href="#{$ethics-id}" class="nav-link">
                  <xsl:choose>
                    <xsl:when test="normalize-space(string($ethics/title))">
                      <xsl:value-of select="normalize-space(string($ethics/title))"/>
                    </xsl:when>
                    <xsl:otherwise>Ethics Statement</xsl:otherwise>
                  </xsl:choose>
                </a>
              </li>
            </xsl:if>
            <xsl:if test="$notes">
              <xsl:variable name="notes-id">
                <xsl:apply-templates select="$notes" mode="id"/>
              </xsl:variable>
              <li>
                <a href="#{$notes-id}" class="nav-link">
                  <xsl:choose>
                    <xsl:when test="normalize-space(string($notes/title))">
                      <xsl:value-of select="normalize-space(string($notes/title))"/>
                    </xsl:when>
                    <xsl:otherwise>Notes</xsl:otherwise>
                  </xsl:choose>
                </a>
              </li>
            </xsl:if>
            <!-- the Bibliography of British Columbia: one link per section -->
            <xsl:for-each select="$reflist[@content-type = 'bibliography-of-bc']/ref-list[ref]">
              <xsl:variable name="sec-id">
                <xsl:apply-templates select="." mode="id"/>
              </xsl:variable>
              <li>
                <a href="#{$sec-id}" class="nav-link">
                  <xsl:value-of select="normalize-space(string(title))"/>
                </a>
              </li>
            </xsl:for-each>
            <xsl:if test="$reflist[not(@content-type = 'bibliography-of-bc')]">
              <xsl:variable name="ref-id">
                <xsl:apply-templates select="$reflist" mode="id"/>
              </xsl:variable>
              <li>
                <a href="#{$ref-id}" class="nav-link">
                  <xsl:choose>
                    <xsl:when test="normalize-space(string($reflist/title))">
                      <xsl:value-of select="normalize-space(string($reflist/title))"/>
                    </xsl:when>
                    <xsl:otherwise>References</xsl:otherwise>
                  </xsl:choose>
                </a>
              </li>
            </xsl:if>
            <xsl:if test="(front/article-meta | front-stub)//bio | back/bio">
              <li><a href="#{$this-article}-bios" class="nav-link">Contributor Bios</a></li>
            </xsl:if>
          </ul>
          </xsl:if>
          <p class="sidebar-back-to-top">
            <a href="#{$this-article}-top" class="nav-link back-to-top-link">
              <xsl:text>&#8593; Back to Top</xsl:text>
            </a>
          </p>
        </div>
      </nav>

      <!-- floating back-to-top, only shows when the sidebar stops being
           sticky on narrow screens -->
      <a href="#{$this-article}-top" class="floating-back-to-top"
         aria-label="Back to top" title="Back to top">
        <xsl:text>&#8593;</xsl:text>
      </a>
    </div>
    <!-- ========================================== -->
    <!-- END OF THE NEW SPLIT GRID LAYOUT WRAPPER   -->
    <!-- ========================================== -->


    <!-- Author bios stay full width underneath, exactly like your original template -->
    <xsl:variable name="bios"
      select="(front/article-meta | front-stub)//bio | back/bio"/>
    <xsl:if test="$bios">
      <div id="{$this-article}-bios" class="author-bios">
        <h2>Contributor Bios</h2>
        <xsl:for-each select="$bios">
          <div class="bio">
            <xsl:apply-templates select="."/>
          </div>
        </xsl:for-each>
      </div>
    </xsl:if>

    <!-- Footer stays full width underneath, exactly like your original template -->
    <div id="{$this-article}-footer" class="footer">
      <xsl:call-template name="footer-metadata"/>
      <xsl:call-template name="footer-licence"/>
      <xsl:call-template name="footer-branding"/>
    </div>

    <!-- Sub-articles stay full width underneath, exactly like your original template -->
    <xsl:apply-templates select="sub-article | response"/>

  </xsl:template>


  <!-- =============================================================== -->
  <!--  SIDEBAR ACTIONS: PDF, share, rights and permissions            -->
  <!--                                                                 -->
  <!--  Share and Rights are <details>/<summary>, not buttons, so they -->
  <!--  open and close with no JavaScript at all. The script at the    -->
  <!--  foot of the page only ADDS things to them (copy-to-clipboard,  -->
  <!--  the phone share sheet, ready-made links to Bluesky and the     -->
  <!--  rest); nothing here depends on it having run.                  -->
  <!-- =============================================================== -->

  <xsl:template name="sidebar-actions">
    <xsl:variable name="meta" select="front/article-meta | front-stub"/>
    <xsl:variable name="pdf"
      select="normalize-space(string($meta/self-uri[@content-type='pdf'][1]/@xlink:href))"/>
    <xsl:variable name="doi"
      select="normalize-space(string($meta/article-id[@pub-id-type='doi'][1]))"/>
    <xsl:variable name="ojs"
      select="normalize-space(string($meta/self-uri[@content-type='ojs'][1]/@xlink:href))"/>
    <!-- What "this article" means to someone you send it to. The DOI is the
         address that keeps working, so it wins; the OJS page is the fallback,
         and an empty string means the script uses the page's own address. -->
    <xsl:variable name="share-url">
      <xsl:choose>
        <xsl:when test="$doi">
          <xsl:text>https://doi.org/</xsl:text>
          <xsl:value-of select="$doi"/>
        </xsl:when>
        <xsl:otherwise><xsl:value-of select="$ojs"/></xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    <!-- Any <license>, with or without an address: an article under the
         journal's copyright agreement has no page to link to yet, and still
         gets the button, showing just the text. -->
    <xsl:variable name="licence" select="$meta/permissions/license[1]"/>

    <xsl:if test="$pdf or $share-url != '' or $licence">
      <div class="sidebar-actions">

        <xsl:if test="$pdf">
          <a class="action-btn action-pdf" href="{$pdf}"
             target="_blank" rel="noopener noreferrer">
            <span class="action-icon" aria-hidden="true">&#8681;</span>
            <xsl:text>PDF</xsl:text>
            <span class="visually-hidden"> (opens in a new tab)</span>
          </a>
        </xsl:if>

        <details class="action-details action-share">
          <summary class="action-btn">
            <span class="action-icon" aria-hidden="true">&#8599;</span>
            <xsl:text>Share</xsl:text>
          </summary>
          <div class="action-panel"
               data-share-url="{$share-url}"
               data-share-title="{normalize-space(string($meta/title-group/article-title[1]))}">
            <p class="action-panel-lead">Link to this article:</p>
            <p class="share-link">
              <xsl:choose>
                <xsl:when test="$share-url != ''">
                  <a href="{$share-url}" rel="noopener noreferrer" target="_blank">
                    <xsl:value-of select="$share-url"/>
                  </a>
                </xsl:when>
                <xsl:otherwise>
                  <span class="share-link-fallback">Use the address in your browser's address bar.</span>
                </xsl:otherwise>
              </xsl:choose>
            </p>
            <!-- filled in by the script; empty and harmless without it -->
            <div class="share-actions"></div>
          </div>
        </details>

        <xsl:if test="$licence">
          <details class="action-details action-rights">
            <summary class="action-btn">
              <span class="action-icon" aria-hidden="true">&#169;</span>
              <xsl:text>Rights and permissions</xsl:text>
            </summary>
            <div class="action-panel">
              <xsl:call-template name="rights-panel">
                <xsl:with-param name="licence" select="$licence"/>
              </xsl:call-template>
            </div>
          </details>
        </xsl:if>

      </div>
    </xsl:if>
  </xsl:template>


  <!-- The contents of the "Rights and permissions" panel. Which of the two
       things it says is decided by the licence's @license-type, which the
       renderer sets from the article's Rights field: "open-access" for a
       Creative Commons article, "copyright" for one published under the
       journal's own agreement. An article has one or the other, never both.
       The address is checked as well, so a file written before the attribute
       existed still gets the right panel. -->
  <xsl:template name="rights-panel">
    <xsl:param name="licence"/>
    <xsl:variable name="href" select="normalize-space(string($licence/@xlink:href))"/>
    <xsl:variable name="is-cc"
      select="contains($href, 'creativecommons.org')
              or $licence/@license-type = 'open-access'"/>

    <xsl:choose>
      <xsl:when test="$is-cc and $href != ''">
        <p class="rights-badge">
          <a href="{$href}" rel="license noopener noreferrer" target="_blank">
            <xsl:call-template name="cc-badge-img">
              <xsl:with-param name="href" select="$href"/>
            </xsl:call-template>
            <span class="visually-hidden"> (opens in a new tab)</span>
          </a>
        </p>
      </xsl:when>
      <xsl:otherwise/>
    </xsl:choose>

    <p class="rights-text">
      <xsl:apply-templates select="$licence/license-p/node()"/>
    </p>

    <!-- No address (the copyright agreement, for now): the text stands
         alone, and the link turns up here once one is set. -->
    <xsl:if test="$href != ''">
      <p class="rights-link">
        <a href="{$href}" rel="license noopener noreferrer" target="_blank">
          <xsl:choose>
            <xsl:when test="$is-cc">Read the full licence</xsl:when>
            <xsl:otherwise>Read the copyright and permissions policy</xsl:otherwise>
          </xsl:choose>
          <span class="visually-hidden"> (opens in a new tab)</span>
        </a>
      </p>
    </xsl:if>

    <!-- One line per ISSN, just above the copyright line:
           ISSN 0005-2949 (Print)
           ISSN 2819-5582 (Online)
         The panel is called from the sidebar, outside <front>, so the
         journal-meta is reached through the licence. -->
    <xsl:for-each select="($licence/ancestor::front | /article/front)[1]/journal-meta/issn[normalize-space(string(.))]">
      <p class="rights-issn">
        <xsl:text>ISSN </xsl:text>
        <xsl:value-of select="normalize-space(string(.))"/>
        <xsl:choose>
          <xsl:when test="@pub-type = 'ppub' or @publication-format = 'print'">
            <xsl:text> (Print)</xsl:text>
          </xsl:when>
          <xsl:when test="@pub-type = 'epub' or @publication-format = 'electronic'">
            <xsl:text> (Online)</xsl:text>
          </xsl:when>
        </xsl:choose>
      </p>
    </xsl:for-each>

    <xsl:variable name="copyright-holder"
      select="normalize-space(string($licence/../copyright-holder))"/>
    <xsl:variable name="copyright-year"
      select="normalize-space(string($licence/../copyright-year))"/>
    <xsl:if test="normalize-space(string($licence/../copyright-statement))">
      <p class="rights-copyright">
        <xsl:text>© </xsl:text>
        <xsl:choose>
          <xsl:when test="$copyright-holder">
            <i class="journal-name"><xsl:value-of select="$copyright-holder"/></i>
            <xsl:if test="$copyright-year">
              <xsl:text>, </xsl:text>
              <xsl:value-of select="$copyright-year"/>
            </xsl:if>
          </xsl:when>
          <xsl:otherwise>
            <xsl:apply-templates select="$licence/../copyright-statement/node()"/>
          </xsl:otherwise>
        </xsl:choose>
      </p>
    </xsl:if>

  </xsl:template>


  <!-- The 88x31 Creative Commons badge matching a licence address. Split out
       of footer-licence so the rights panel and the footer cannot drift. -->
  <xsl:template name="cc-badge-img">
    <xsl:param name="href"/>
    <xsl:choose>
      <xsl:when test="contains($href, 'by-nc-nd')">
        <img alt="Creative Commons Attribution-NonCommercial-NoDerivatives licence" src="https://i.creativecommons.org/l/by-nc-nd/4.0/88x31.png" width="88" height="31"/>
      </xsl:when>
      <xsl:when test="contains($href, 'by-nc-sa')">
        <img alt="Creative Commons Attribution-NonCommercial-ShareAlike licence" src="https://i.creativecommons.org/l/by-nc-sa/4.0/88x31.png" width="88" height="31"/>
      </xsl:when>
      <xsl:when test="contains($href, 'by-nc')">
        <img alt="Creative Commons Attribution-NonCommercial licence" src="https://i.creativecommons.org/l/by-nc/4.0/88x31.png" width="88" height="31"/>
      </xsl:when>
      <xsl:when test="contains($href, 'by-nd')">
        <img alt="Creative Commons Attribution-NoDerivatives licence" src="https://i.creativecommons.org/l/by-nd/4.0/88x31.png" width="88" height="31"/>
      </xsl:when>
      <xsl:when test="contains($href, 'by-sa')">
        <img alt="Creative Commons Attribution-ShareAlike licence" src="https://i.creativecommons.org/l/by-sa/4.0/88x31.png" width="88" height="31"/>
      </xsl:when>
      <xsl:when test="contains($href, 'creativecommons')">
        <img alt="Creative Commons Attribution licence" src="https://i.creativecommons.org/l/by/4.0/88x31.png" width="88" height="31"/>
      </xsl:when>
      <xsl:otherwise>
        <xsl:value-of select="$href"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>


  <!-- =============================================================== -->
  <!--  HOW TO CITE: Chicago, MLA and APA                              -->
  <!-- =============================================================== -->

  <xsl:template name="sidebar-cite">
    <div class="sidebar-meta-card">
      <h2 class="sidebar-heading" id="how-to-cite">How to Cite</h2>
      <div class="cite-widget">
        <div class="cite-tabs" role="tablist" aria-labelledby="how-to-cite">
          <button type="button" class="cite-tab is-current" role="tab"
                  id="cite-tab-chicago" aria-controls="cite-panel-chicago"
                  aria-selected="true">Chicago</button>
          <button type="button" class="cite-tab" role="tab"
                  id="cite-tab-mla" aria-controls="cite-panel-mla"
                  aria-selected="false" tabindex="-1">MLA</button>
          <button type="button" class="cite-tab" role="tab"
                  id="cite-tab-apa" aria-controls="cite-panel-apa"
                  aria-selected="false" tabindex="-1">APA</button>
        </div>

        <div class="cite-panel is-current" id="cite-panel-chicago"
             role="tabpanel" aria-labelledby="cite-tab-chicago">
          <p class="cite-panel-label">Chicago</p>
          <p class="sidebar-citation-box cite-text">
            <xsl:call-template name="citation-chicago"/>
          </p>
        </div>

        <div class="cite-panel" id="cite-panel-mla"
             role="tabpanel" aria-labelledby="cite-tab-mla">
          <p class="cite-panel-label">MLA</p>
          <p class="sidebar-citation-box cite-text">
            <xsl:call-template name="citation-mla"/>
          </p>
        </div>

        <div class="cite-panel" id="cite-panel-apa"
             role="tabpanel" aria-labelledby="cite-tab-apa">
          <p class="cite-panel-label">APA</p>
          <p class="sidebar-citation-box cite-text">
            <xsl:call-template name="citation-apa"/>
          </p>
        </div>

        <!-- the script turns this into a working copy button -->
        <div class="cite-copy-wrap"></div>
      </div>
    </div>
  </xsl:template>


  <!-- Frohlick, Susan, and Nassim Zand Dizari. "Okanagan Summer Tourism
       Sounds: A Feminist Sonic Ethnography." BC Studies, no. 230 (Summer
       2026): 93-112. https://doi.org/10.14288/bcs.no230.200416. -->
  <xsl:template name="citation-chicago">
    <xsl:call-template name="chicago-author-string"/>
    <xsl:text> &#8220;</xsl:text>
    <xsl:call-template name="cite-title">
      <xsl:with-param name="single-quotes" select="true()"/>
    </xsl:call-template>
    <xsl:text>&#8221; </xsl:text>
    <cite><xsl:call-template name="cite-journal-name"/></cite>
    <xsl:call-template name="cite-issue">
      <xsl:with-param name="lead" select="', no. '"/>
    </xsl:call-template>
    <xsl:call-template name="cite-date-parens"/>
    <xsl:call-template name="cite-pages">
      <xsl:with-param name="lead" select="': '"/>
    </xsl:call-template>
    <xsl:text>.</xsl:text>
    <xsl:call-template name="cite-doi">
      <xsl:with-param name="lead" select="' '"/>
      <xsl:with-param name="stop" select="'.'"/>
    </xsl:call-template>
  </xsl:template>


  <!-- Frohlick, Susan, and Nassim Zand Dizari. "Okanagan Summer Tourism
       Sounds: A Feminist Sonic Ethnography." BC Studies, no. 230, 2026,
       pp. 93-112, https://doi.org/10.14288/bcs.no230.200416. -->
  <xsl:template name="citation-mla">
    <xsl:call-template name="mla-author-string"/>
    <xsl:text> &#8220;</xsl:text>
    <xsl:call-template name="cite-title">
      <xsl:with-param name="single-quotes" select="true()"/>
    </xsl:call-template>
    <xsl:text>&#8221; </xsl:text>
    <cite><xsl:call-template name="cite-journal-name"/></cite>
    <xsl:call-template name="cite-issue">
      <xsl:with-param name="lead" select="', no. '"/>
    </xsl:call-template>
    <xsl:call-template name="cite-year">
      <xsl:with-param name="lead" select="', '"/>
    </xsl:call-template>
    <xsl:call-template name="cite-pages">
      <xsl:with-param name="lead" select="', pp. '"/>
      <xsl:with-param name="lead-single" select="', p. '"/>
    </xsl:call-template>
    <xsl:call-template name="cite-doi">
      <xsl:with-param name="lead" select="', '"/>
    </xsl:call-template>
    <xsl:text>.</xsl:text>
  </xsl:template>


  <!-- Frohlick, S., &amp; Dizari, N. Z. (2026). Okanagan Summer Tourism
       Sounds: A feminist sonic ethnography. BC Studies, (230), 93-112.
       https://doi.org/10.14288/bcs.no230.200416 -->
  <xsl:template name="citation-apa">
    <xsl:call-template name="apa-author-string"/>
    <xsl:call-template name="cite-year">
      <xsl:with-param name="lead" select="' ('"/>
      <xsl:with-param name="tail" select="'). '"/>
      <xsl:with-param name="when-missing" select="' (n.d.). '"/>
    </xsl:call-template>
    <xsl:call-template name="cite-title"/>
    <xsl:text> </xsl:text>
    <cite><xsl:call-template name="cite-journal-name"/></cite>
    <xsl:call-template name="cite-issue">
      <xsl:with-param name="lead" select="', ('"/>
      <xsl:with-param name="tail" select="')'"/>
    </xsl:call-template>
    <xsl:call-template name="cite-pages">
      <xsl:with-param name="lead" select="', '"/>
    </xsl:call-template>
    <xsl:text>.</xsl:text>
    <xsl:call-template name="cite-doi">
      <xsl:with-param name="lead" select="' '"/>
    </xsl:call-template>
  </xsl:template>


  <!-- Pieces the three styles share. -->

  <!-- Title, with the subtitle joined on after a colon, and a full stop
       after it. The editor stores title and subtitle apart so the galley can
       set the subtitle on its own line; a citation wants them as one string.

       Chicago and MLA wrap the title in double quotation marks, so any
       quotation inside the title drops to single marks (single-quotes):
       "'They Would Not Permit Us to Work the Coals': Indigenous Origins ..."
       and not ""They Would ..."

       The stop is left off when the title already ends in its own
       punctuation ("Camas Nullius?" must not become "Camas Nullius?."), and
       goes inside a closing quotation mark when the title ends in one. -->
  <xsl:template name="cite-title">
    <xsl:param name="single-quotes" select="false()"/>
    <xsl:variable name="meta" select="front/article-meta | front-stub"/>
    <xsl:variable name="tnode" select="$meta/title-group/article-title[1]"/>
    <xsl:variable name="snode" select="$meta/title-group/subtitle[1]"/>
    <xsl:variable name="t" select="normalize-space(string($tnode))"/>
    <xsl:variable name="s" select="normalize-space(string($snode))"/>
    <xsl:variable name="joined">
      <xsl:value-of select="$t"/>
      <xsl:if test="$s">
        <xsl:if test="not(contains(':?!', substring($t, string-length($t))))">
          <xsl:text>:</xsl:text>
        </xsl:if>
        <xsl:text> </xsl:text>
        <xsl:value-of select="$s"/>
      </xsl:if>
    </xsl:variable>
    <xsl:variable name="full">
      <xsl:choose>
        <xsl:when test="$single-quotes">
          <!-- In variables because XPath 1.0 cannot put a straight
               apostrophe inside a quoted literal. -->
          <xsl:variable name="doubles">&#8220;&#8221;&quot;</xsl:variable>
          <xsl:variable name="singles">&#8216;&#8217;&#39;</xsl:variable>
          <xsl:value-of select="translate($joined, $doubles, $singles)"/>
        </xsl:when>
        <xsl:otherwise><xsl:value-of select="$joined"/></xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    <xsl:variable name="len" select="string-length($full)"/>
    <xsl:variable name="last" select="substring($full, $len)"/>
    <!-- Ends in a closing quotation mark: 'Coals.' not 'Coals'. A final
         right single mark counts only when the title opens one too, so a
         closing apostrophe ("the Settlers'") still takes its stop after. -->
    <xsl:variable name="quote-end" select="$len &gt; 1 and
                    (contains('&#8221;&quot;', substring($joined, $len))
                     or (substring($joined, $len) = '&#8217;' and contains($joined, '&#8216;')))"/>
    <!-- The words themselves come from the title's nodes rather than its
         string, so a book or case name italicized in the title stays
         italic in the citation. The text node the title ends on loses its
         closing quotation mark when the stop has to go inside it. -->
    <xsl:variable name="end-el" select="$snode[normalize-space()] | $tnode[not($snode[normalize-space()])]"/>
    <xsl:variable name="end-text" select="($end-el//text()[normalize-space()])[last()]"/>
    <xsl:apply-templates select="$tnode/node()" mode="cite-inline">
      <xsl:with-param name="single-quotes" select="$single-quotes"/>
      <xsl:with-param name="end-text" select="$end-text"/>
      <xsl:with-param name="drop-last" select="$quote-end"/>
    </xsl:apply-templates>
    <xsl:if test="$s">
      <xsl:if test="not(contains(':?!', substring($t, string-length($t))))">
        <xsl:text>:</xsl:text>
      </xsl:if>
      <xsl:text> </xsl:text>
      <xsl:apply-templates select="$snode/node()" mode="cite-inline">
        <xsl:with-param name="single-quotes" select="$single-quotes"/>
        <xsl:with-param name="end-text" select="$end-text"/>
        <xsl:with-param name="drop-last" select="$quote-end"/>
      </xsl:apply-templates>
    </xsl:if>
    <xsl:choose>
      <xsl:when test="$quote-end">
        <xsl:if test="not(contains('.?!', substring($full, $len - 1, 1)))">
          <xsl:text>.</xsl:text>
        </xsl:if>
        <xsl:value-of select="$last"/>
      </xsl:when>
      <xsl:otherwise>
        <xsl:if test="not(contains('.?!', $last))">
          <xsl:text>.</xsl:text>
        </xsl:if>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <!-- Title words inside a citation: italics kept, everything else reduced
       to its text, footnote callouts dropped. -->
  <xsl:template match="text()" mode="cite-inline">
    <xsl:param name="single-quotes" select="false()"/>
    <xsl:param name="end-text"/>
    <xsl:param name="drop-last" select="false()"/>
    <xsl:variable name="raw">
      <xsl:choose>
        <xsl:when test="$drop-last and generate-id(.) = generate-id($end-text)">
          <!-- the renderer trims the title, so the mark is the last character -->
          <xsl:value-of select="substring(., 1, string-length(.) - 1)"/>
        </xsl:when>
        <xsl:otherwise><xsl:value-of select="."/></xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    <xsl:choose>
      <xsl:when test="$single-quotes">
        <xsl:variable name="doubles">&#8220;&#8221;&quot;</xsl:variable>
        <xsl:variable name="singles">&#8216;&#8217;&#39;</xsl:variable>
        <xsl:value-of select="translate($raw, $doubles, $singles)"/>
      </xsl:when>
      <xsl:otherwise><xsl:value-of select="$raw"/></xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <xsl:template match="italic" mode="cite-inline">
    <xsl:param name="single-quotes" select="false()"/>
    <xsl:param name="end-text"/>
    <xsl:param name="drop-last" select="false()"/>
    <i>
      <xsl:apply-templates mode="cite-inline">
        <xsl:with-param name="single-quotes" select="$single-quotes"/>
        <xsl:with-param name="end-text" select="$end-text"/>
        <xsl:with-param name="drop-last" select="$drop-last"/>
      </xsl:apply-templates>
    </i>
  </xsl:template>

  <xsl:template match="xref | fn" mode="cite-inline"/>

  <xsl:template match="*" mode="cite-inline">
    <xsl:param name="single-quotes" select="false()"/>
    <xsl:param name="end-text"/>
    <xsl:param name="drop-last" select="false()"/>
    <xsl:apply-templates mode="cite-inline">
      <xsl:with-param name="single-quotes" select="$single-quotes"/>
      <xsl:with-param name="end-text" select="$end-text"/>
      <xsl:with-param name="drop-last" select="$drop-last"/>
    </xsl:apply-templates>
  </xsl:template>

  <xsl:template name="cite-journal-name">
    <xsl:choose>
      <xsl:when test="normalize-space(string(front/journal-meta//abbrev-journal-title[1]))">
        <xsl:value-of select="normalize-space(string(front/journal-meta//abbrev-journal-title[1]))"/>
      </xsl:when>
      <xsl:otherwise>
        <xsl:value-of select="normalize-space(string(front/journal-meta//journal-title[1]))"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <!-- The editor writes the literal string UNKNOWN into a draft when an issue
       number or year has not been filled in yet. Never surface that to a
       reader; leave the slot out instead. -->
  <xsl:template name="cite-issue">
    <xsl:param name="lead" select="', no. '"/>
    <xsl:param name="tail" select="''"/>
    <xsl:variable name="meta" select="front/article-meta | front-stub"/>
    <xsl:if test="normalize-space(string($meta/issue)) and not($meta/issue = 'UNKNOWN')">
      <xsl:value-of select="$lead"/>
      <xsl:value-of select="normalize-space(string($meta/issue))"/>
      <xsl:value-of select="$tail"/>
    </xsl:if>
  </xsl:template>

  <xsl:template name="cite-year">
    <xsl:param name="lead" select="''"/>
    <xsl:param name="tail" select="''"/>
    <xsl:param name="when-missing" select="''"/>
    <xsl:variable name="meta" select="front/article-meta | front-stub"/>
    <!-- The date a citation wants is the one the issue is dated, not the day
         the file went up: "BC Studies no. 230 (Summer 2026)". Picking it with
         a union and [1] does not work: a union is in document order, so
         [1] returns whichever pub-date happens to come first in the file,
         which is the epub date and which has no season. Each candidate is
         therefore guarded on the one before it. -->
    <xsl:variable name="collection" select="$meta/pub-date[@pub-type='collection'][1]"/>
    <xsl:variable name="ppub" select="$meta/pub-date[@pub-type='ppub'][1]"/>
    <xsl:variable name="d"
      select="$collection
              | $ppub[not($collection)]
              | $meta/pub-date[1][not($collection) and not($ppub)]"/>
    <xsl:choose>
      <xsl:when test="normalize-space(string($d/year)) and not($d/year = 'UNKNOWN')">
        <xsl:value-of select="$lead"/>
        <xsl:value-of select="normalize-space(string($d/year))"/>
        <xsl:value-of select="$tail"/>
      </xsl:when>
      <xsl:otherwise><xsl:value-of select="$when-missing"/></xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <!-- Chicago puts the season and year in brackets after the issue. -->
  <xsl:template name="cite-date-parens">
    <xsl:variable name="meta" select="front/article-meta | front-stub"/>
    <!-- The date a citation wants is the one the issue is dated, not the day
         the file went up: "BC Studies no. 230 (Summer 2026)". Picking it with
         a union and [1] does not work: a union is in document order, so
         [1] returns whichever pub-date happens to come first in the file,
         which is the epub date and which has no season. Each candidate is
         therefore guarded on the one before it. -->
    <xsl:variable name="collection" select="$meta/pub-date[@pub-type='collection'][1]"/>
    <xsl:variable name="ppub" select="$meta/pub-date[@pub-type='ppub'][1]"/>
    <xsl:variable name="d"
      select="$collection
              | $ppub[not($collection)]
              | $meta/pub-date[1][not($collection) and not($ppub)]"/>
    <xsl:if test="normalize-space(string($d/year)) and not($d/year = 'UNKNOWN')">
      <xsl:text> (</xsl:text>
      <xsl:if test="normalize-space(string($d/season))">
        <xsl:value-of select="normalize-space(string($d/season))"/>
        <xsl:text> </xsl:text>
      </xsl:if>
      <xsl:value-of select="normalize-space(string($d/year))"/>
      <xsl:text>)</xsl:text>
    </xsl:if>
  </xsl:template>

  <xsl:template name="cite-pages">
    <xsl:param name="lead" select="': '"/>
    <!-- MLA distinguishes "p. 7" from "pp. 7-9"; the others do not, and fall
         back to $lead. -->
    <xsl:param name="lead-single" select="$lead"/>
    <xsl:variable name="meta" select="front/article-meta | front-stub"/>
    <xsl:variable name="f" select="normalize-space(string($meta/fpage))"/>
    <xsl:variable name="l" select="normalize-space(string($meta/lpage))"/>
    <xsl:if test="$f">
      <xsl:choose>
        <xsl:when test="$l and $l != $f"><xsl:value-of select="$lead"/></xsl:when>
        <xsl:otherwise><xsl:value-of select="$lead-single"/></xsl:otherwise>
      </xsl:choose>
      <xsl:value-of select="$f"/>
      <xsl:if test="$l and $l != $f">
        <xsl:text>&#8211;</xsl:text>
        <xsl:value-of select="$l"/>
      </xsl:if>
    </xsl:if>
  </xsl:template>

  <xsl:template name="cite-doi">
    <xsl:param name="lead" select="' '"/>
    <xsl:param name="stop" select="''"/>
    <xsl:variable name="meta" select="front/article-meta | front-stub"/>
    <xsl:variable name="doi"
      select="normalize-space(string($meta/article-id[@pub-id-type='doi'][1]))"/>
    <xsl:if test="$doi">
      <xsl:value-of select="$lead"/>
      <xsl:text>https://doi.org/</xsl:text>
      <xsl:value-of select="$doi"/>
      <xsl:value-of select="$stop"/>
    </xsl:if>
  </xsl:template>


  <!-- =============================================================== -->
  <!--  MLA author string.                                             -->
  <!--  1 author  : Surname, Given.                                    -->
  <!--  2 authors : Surname, Given, and Given Surname.                 -->
  <!--  3+ authors: Surname, Given, et al.                             -->
  <!-- =============================================================== -->

  <xsl:template name="mla-author-string">
    <xsl:variable name="authors"
      select="(front/article-meta | front-stub)/contrib-group[not(@content-type)]/contrib[
                not(@contrib-type) or @contrib-type='author']"/>
    <xsl:if test="count($authors) &gt; 0">
      <xsl:variable name="names">
        <xsl:for-each select="$authors">
          <xsl:choose>
            <xsl:when test="position() = 1">
              <xsl:call-template name="name-inverted"/>
            </xsl:when>
            <!-- three or more: everyone after the first is "et al." -->
            <xsl:when test="count($authors) &gt; 2">
              <xsl:if test="position() = 2">
                <xsl:text>, et al</xsl:text>
              </xsl:if>
            </xsl:when>
            <xsl:otherwise>
              <xsl:text>, and </xsl:text>
              <xsl:call-template name="name-natural"/>
            </xsl:otherwise>
          </xsl:choose>
        </xsl:for-each>
      </xsl:variable>
      <xsl:call-template name="stopped">
        <xsl:with-param name="text" select="$names"/>
      </xsl:call-template>
    </xsl:if>
  </xsl:template>


  <!-- =============================================================== -->
  <!--  APA author string: surnames with initials throughout.          -->
  <!--  1 author  : Surname, G.                                        -->
  <!--  2 authors : Surname, G., &amp; Surname, G.                     -->
  <!--  3+ authors: Surname, G., Surname, G., &amp; Surname, G.        -->
  <!-- =============================================================== -->

  <xsl:template name="apa-author-string">
    <xsl:variable name="authors"
      select="(front/article-meta | front-stub)/contrib-group[not(@content-type)]/contrib[
                not(@contrib-type) or @contrib-type='author']"/>
    <xsl:if test="count($authors) &gt; 0">
      <xsl:for-each select="$authors">
        <xsl:if test="position() &gt; 1">
          <xsl:choose>
            <xsl:when test="count($authors) = 2"><xsl:text>, &amp; </xsl:text></xsl:when>
            <xsl:when test="position() = last()"><xsl:text>, &amp; </xsl:text></xsl:when>
            <xsl:otherwise><xsl:text>, </xsl:text></xsl:otherwise>
          </xsl:choose>
        </xsl:if>
        <xsl:choose>
          <xsl:when test="normalize-space(string(name/surname))">
            <xsl:value-of select="normalize-space(string(name/surname))"/>
            <xsl:if test="normalize-space(string(name/given-names))">
              <xsl:text>, </xsl:text>
              <xsl:call-template name="initials">
                <xsl:with-param name="given"
                  select="normalize-space(string(name/given-names))"/>
              </xsl:call-template>
            </xsl:if>
          </xsl:when>
          <xsl:when test="collab">
            <xsl:value-of select="normalize-space(string(collab))"/>
          </xsl:when>
        </xsl:choose>
      </xsl:for-each>
    </xsl:if>
  </xsl:template>


  <!-- Given names as initials, for APA.
         "Nassim Zand"  -> "N. Z."
         "Toni-Leah C." -> "T.-L. C."
         "J."           -> "J."      (already an initial; left alone)

       One initial per call. The separator to print in front of it is passed
       in as a parameter rather than pushed back onto the front of the
       remaining text: a leading hyphen would be split on again, and the
       template would call itself with the same string forever. Each call
       also consumes at least one character, so the recursion cannot run
       away even on a name shaped in some way not thought of here. -->
  <xsl:template name="initials">
    <xsl:param name="given"/>
    <xsl:param name="sep" select="''"/>
    <xsl:variable name="g" select="normalize-space($given)"/>
    <xsl:if test="$g != ''">
      <!-- The first part of the name, where a part ends at a space, a hyphen
           or a full stop, whichever comes first. XPath 1.0 cannot look for
           "the first of these three", so each substring-before narrows the
           one before it: up to the first space, then up to a hyphen inside
           that, then up to a full stop inside that. The full stop matters
           for a name already written as initials: "Y.C." is two of them,
           not one. -->
      <xsl:variable name="to-space" select="substring-before(concat($g, ' '), ' ')"/>
      <xsl:variable name="to-hyphen" select="substring-before(concat($to-space, '-'), '-')"/>
      <xsl:variable name="head" select="substring-before(concat($to-hyphen, '.'), '.')"/>
      <!-- the character that ended it, and everything after it -->
      <xsl:variable name="delim" select="substring($g, string-length($head) + 1, 1)"/>
      <xsl:variable name="rest" select="substring($g, string-length($head) + 2)"/>

      <xsl:if test="$head != ''">
        <xsl:value-of select="$sep"/>
        <xsl:value-of select="substring($head, 1, 1)"/>
        <xsl:text>.</xsl:text>
      </xsl:if>

      <xsl:if test="normalize-space($rest) != ''">
        <xsl:call-template name="initials">
          <xsl:with-param name="given" select="$rest"/>
          <xsl:with-param name="sep">
            <xsl:choose>
              <xsl:when test="$delim = '-'">-</xsl:when>
              <xsl:otherwise><xsl:text> </xsl:text></xsl:otherwise>
            </xsl:choose>
          </xsl:with-param>
        </xsl:call-template>
      </xsl:if>
    </xsl:if>
  </xsl:template>


  <!-- "Surname, Given Suffix" -->
  <xsl:template name="name-inverted">
    <xsl:choose>
      <xsl:when test="normalize-space(string(name/surname))">
        <xsl:value-of select="normalize-space(string(name/surname))"/>
        <xsl:if test="normalize-space(string(name/given-names))">
          <xsl:text>, </xsl:text>
          <xsl:value-of select="normalize-space(string(name/given-names))"/>
        </xsl:if>
        <xsl:if test="normalize-space(string(name/suffix))">
          <xsl:text>, </xsl:text>
          <xsl:value-of select="normalize-space(string(name/suffix))"/>
        </xsl:if>
      </xsl:when>
      <xsl:when test="collab">
        <xsl:value-of select="normalize-space(string(collab))"/>
      </xsl:when>
    </xsl:choose>
  </xsl:template>

  <!-- "Given Surname" -->
  <xsl:template name="name-natural">
    <xsl:choose>
      <xsl:when test="normalize-space(string(name/surname))">
        <xsl:if test="normalize-space(string(name/given-names))">
          <xsl:value-of select="normalize-space(string(name/given-names))"/>
          <xsl:text> </xsl:text>
        </xsl:if>
        <xsl:value-of select="normalize-space(string(name/surname))"/>
      </xsl:when>
      <xsl:when test="collab">
        <xsl:value-of select="normalize-space(string(collab))"/>
      </xsl:when>
    </xsl:choose>
  </xsl:template>


  <!-- =============================================================== -->
  <!--  Chicago author string for the "How to Cite" box.               -->
  <!--  1 author  : Surname, Given.                                    -->
  <!--  2 authors : Surname, Given, and Given Surname.                 -->
  <!--  3+ authors: Surname, Given, Given Surname, and Given Surname.  -->
  <!--  Issue editors sit in their own contrib-group and are skipped.  -->
  <!-- =============================================================== -->

  <xsl:template name="chicago-author-string">
    <xsl:variable name="authors"
      select="(front/article-meta | front-stub)/contrib-group[not(@content-type)]/contrib[
                not(@contrib-type) or @contrib-type='author']"/>
    <xsl:choose>
      <xsl:when test="count($authors) = 0"/>
      <xsl:otherwise>
        <xsl:variable name="names">
        <xsl:for-each select="$authors">
          <xsl:choose>
            <!-- first author, inverted -->
            <xsl:when test="position() = 1">
              <xsl:choose>
                <xsl:when test="normalize-space(string(name/surname))">
                  <xsl:value-of select="normalize-space(string(name/surname))"/>
                  <xsl:if test="normalize-space(string(name/given-names))">
                    <xsl:text>, </xsl:text>
                    <xsl:value-of select="normalize-space(string(name/given-names))"/>
                  </xsl:if>
                  <xsl:if test="normalize-space(string(name/suffix))">
                    <xsl:text>, </xsl:text>
                    <xsl:value-of select="normalize-space(string(name/suffix))"/>
                  </xsl:if>
                </xsl:when>
                <xsl:when test="collab">
                  <xsl:value-of select="normalize-space(string(collab))"/>
                </xsl:when>
              </xsl:choose>
            </xsl:when>
            <!-- the rest, in natural order (a Chicago bibliography entry
                 lists every author; "et al." is for the notes) -->
            <xsl:otherwise>
              <xsl:choose>
                <xsl:when test="count($authors) = 2"><xsl:text>, and </xsl:text></xsl:when>
                <xsl:when test="position() = last()"><xsl:text>, and </xsl:text></xsl:when>
                <xsl:otherwise><xsl:text>, </xsl:text></xsl:otherwise>
              </xsl:choose>
              <xsl:choose>
                <xsl:when test="normalize-space(string(name/surname))">
                  <xsl:if test="normalize-space(string(name/given-names))">
                    <xsl:value-of select="normalize-space(string(name/given-names))"/>
                    <xsl:text> </xsl:text>
                  </xsl:if>
                  <xsl:value-of select="normalize-space(string(name/surname))"/>
                </xsl:when>
                <xsl:when test="collab">
                  <xsl:value-of select="normalize-space(string(collab))"/>
                </xsl:when>
              </xsl:choose>
            </xsl:otherwise>
          </xsl:choose>
        </xsl:for-each>
        </xsl:variable>
        <xsl:call-template name="stopped">
          <xsl:with-param name="text" select="$names"/>
        </xsl:call-template>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>


  <!-- Print a string and close it with a full stop, unless it already ends
       in one. A name written as initials ("Michael Y.C.") supplies its own,
       and "Y.C.." is not something to put in a citation. -->
  <xsl:template name="stopped">
    <xsl:param name="text"/>
    <xsl:value-of select="$text"/>
    <xsl:if test="substring($text, string-length($text)) != '.'">
      <xsl:text>.</xsl:text>
    </xsl:if>
  </xsl:template>


  <!-- =============================================================== -->
  <!--  Copyright line at the foot of the galley.                      -->
  <!--                                                                 -->
  <!--  The licence itself used to be printed here as well, badge and  -->
  <!--  all. It now lives behind the sidebar's "Rights and permissions" -->
  <!--  button, where a reader looking for it will actually find it,    -->
  <!--  and is not repeated at the bottom of the page. Nothing is lost  -->
  <!--  to a machine reading the file: <license> is still in the XML,   -->
  <!--  which is where Crossref, OJS and the harvesters read it from.   -->
  <!--                                                                 -->
  <!--  The copyright statement stays: it names who holds copyright in  -->
  <!--  this particular article, which the licence does not.            -->
  <!-- =============================================================== -->

  <xsl:template name="footer-licence">
    <xsl:for-each select="(front/article-meta | front-stub)/permissions">
      <xsl:if test="normalize-space(string(copyright-statement))">
        <div class="licence-block">
          <p class="copyright-line">
            <xsl:apply-templates select="copyright-statement/node()"/>
          </p>
        </div>
      </xsl:if>
    </xsl:for-each>
  </xsl:template>


  <xsl:template match="front | front-stub">
    <!-- First Table: journal and article metadata -->
    <div class="metadata two-column table">
      <div class="row">
        <!-- Cell 1: journal information -->
        <xsl:for-each select="journal-meta">
          <!-- (journal-id+, journal-title-group*, (contrib-group | aff | aff-alternatives)*,
                issn+, issn-l?, isbn*, publisher?, notes*, self-uri*)         -->
          <div class="cell">
            <h2 class="generated-hidden">
              <xsl:text>Journal Information</xsl:text>
            </h2>
            <div class="metadata-group">
              <xsl:apply-templates select="journal-id | journal-title-group" mode="metadata"/>
              <!-- the following may appear in 2.3 -->
              <xsl:apply-templates mode="metadata" select="journal-title | journal-subtitle | trans-title | trans-subtitle | abbrev-journal-title"/>
              <!-- contrib-group, aff, aff-alternatives, author-notes -->
              <xsl:apply-templates mode="metadata"
                select="contrib-group"/>
              <xsl:if test="aff | aff-alternatives | author-notes">
                <div class="metadata-group">
                  <xsl:apply-templates mode="metadata"
                    select="aff | aff-alternatives | author-notes"/>
                </div>
              </xsl:if>
              <xsl:apply-templates select="issn | issn-l | isbn | publisher | notes | self-uri" mode="metadata"/>
            </div>
          </div>
        </xsl:for-each>

        <!-- Cell 2: Article information -->
        <xsl:for-each select="article-meta | self::front-stub">
          <!-- content model:
				    (article-id*, article-categories?, title-group,
				     (contrib-group | aff)*, 
             author-notes?, pub-date+, volume?, volume-id*,
             volume-series?, issue?, issue-id*, issue-title*,
             issue-sponsor*, issue-part?, isbn*, supplement?, 
             ((fpage, lpage?, page-range?) | elocation-id)?, 
             (email | ext-link | uri | product | 
              supplementary-material)*, 
             history?, permissions?, self-uri*, related-article*, 
             abstract*, trans-abstract*, 
             kwd-group*, funding-group*, conference*, counts?,
             custom-meta-group?)
            
            These are handled as follows:

            In the "Article Information" header cell:
              article-id
              pub-date
              volume
              volume-id
              volume-series
              issue
              issue-id
              issue-title
              issue-sponsor
              issue-part
              isbn
              supplement
              fpage
              lpage
              page-range
              elocation-id
              email
              ext-link
              uri
              product
              history
              permissions
              self-uri
              related-article
              funding-group
              conference

            In the "Article title" cell:
              title-group
              contrib-group
              aff
              author-notes
              abstract
              trans-abstract

            In the metadata footer
              article-categories
              supplementary-material
              kwd-group
              counts
              custom-meta-group

				  -->

          <div class="cell">
            <h2 class="generated-hidden">
              <xsl:text>Article Information</xsl:text>
            </h2>
            <div class="metadata-group">

              <xsl:apply-templates mode="metadata"
                select="email | ext-link | uri | self-uri"/>

              <xsl:apply-templates mode="metadata" select="product"/>

              <!-- permissions (copyright and licence) are printed at the
                   foot of the galley by footer-licence, not here -->
              
              <xsl:apply-templates mode="metadata" select="history/date"/>

              <xsl:apply-templates mode="metadata" select="pub-date"/>

              <xsl:call-template name="volume-info">
                <!-- handles volume?, volume-id*, volume-series? -->
              </xsl:call-template>

              <xsl:call-template name="issue-info">
                <!-- handles issue?, issue-id*, issue-title*,
                     issue-sponsor*, issue-part? -->
              </xsl:call-template>

              <xsl:call-template name="page-info">
                <!-- handles (fpage, lpage?, page-range?) -->
              </xsl:call-template>

              <xsl:apply-templates mode="metadata" select="elocation-id"/>

              <xsl:apply-templates mode="metadata" select="isbn"/>

              <xsl:apply-templates mode="metadata"
                select="supplement | related-article | conference"/>

              <xsl:apply-templates mode="metadata" select="article-id"/>

              <!-- only in 2.3 -->
              <xsl:apply-templates mode="metadata" select="contract-num | contract-sponsor |
                grant-num | grant-sponsor"/>
                
              <xsl:apply-templates mode="metadata" select="funding-group/*">
                <!-- includes (award-group*, funding-statement*,
                     open-access?) -->
              </xsl:apply-templates>
            </div>
          </div>
        </xsl:for-each>
      </div>
    </div>
    

    
      <!-- change context to front/article-meta (again) -->
      <xsl:for-each select="article-meta | self::front-stub">
        <div class="metadata title-block">
          <xsl:call-template name="section-tag"/>
          <xsl:apply-templates mode="metadata" select="title-group"/>
        </div>
        <!-- house style: a rule closes the title block and opens the
             byline. Presentational, so it carries no heading semantics and
             is hidden from assistive technology - a screen reader gets the
             separation from the h1 and the byline themselves. -->
        <hr class="title-rule" aria-hidden="true"/>
        <!-- contrib-group, aff, aff-alternatives, author-notes -->
        <!-- authors only: issue editors stay in the XML metadata but are
             not printed at the top of the galley -->
        <xsl:apply-templates mode="metadata"
          select="contrib-group[not(@content-type = 'editor')]"/>
        <xsl:call-template name="journal-line"/>
        <!-- back in article-meta or front-stub context -->
        <xsl:if test="aff | aff-alternatives | author-notes">
          <div class="metadata two-column table">
            <div class="row">
            <div class="cell empty"/>
            <div class="cell">
              <div class="metadata-group">
                <xsl:apply-templates mode="metadata"
                  select="aff | aff-alternatives | author-notes"/>
              </div>
            </div>
            </div>
          </div>
        </xsl:if>


        <!-- audio clips, before the abstract: in a podcast or soundwork the
             recording is the article, so the reader meets it first rather
             than after the front matter. They are <media> elements in the
             body of the XML; only their position on the page moves. -->
        <xsl:call-template name="audio-playlist">
          <xsl:with-param name="clips"
            select="ancestor::*[self::article or self::sub-article][1]
                    /body//media[@mimetype='audio']"/>
        </xsl:call-template>

        <!-- abstract(s) -->
        <xsl:if test="abstract | trans-abstract">
          <!-- rule separates title+authors from abstract(s) -->

          <xsl:for-each select="abstract | trans-abstract">
            <div class="abstract-section">
              <xsl:if test="position() = 1">
                <!-- outline target: put the id on the abstract itself, not at
                     the top of the front matter -->
                <xsl:attribute name="id">abstract-sec</xsl:attribute>
              </xsl:if>
              <h2 class="title-abstract">
                <xsl:choose>
                  <xsl:when test="normalize-space(string(title))">
                    <xsl:apply-templates select="title/node()"/>
                  </xsl:when>
                  <xsl:when test="self::trans-abstract">Translated Abstract</xsl:when>
                  <xsl:otherwise>Abstract</xsl:otherwise>
                </xsl:choose>
              </h2>
              <xsl:apply-templates select="*[not(self::title)]"/>
            </div>
          </xsl:for-each>
          <!-- end of abstract or trans-abstract -->
        </xsl:if>
        <xsl:if test="kwd-group">
          <xsl:apply-templates mode="metadata" select="kwd-group"/>
        </xsl:if>
        <!-- end of dealing with abstracts -->
      </xsl:for-each>
      <xsl:for-each select="notes">
            <div class="metadata">
              <xsl:apply-templates mode="metadata" select="."/>
            </div>
      </xsl:for-each>
    
    <!-- end of big front-matter pull -->
  </xsl:template>

 
  <xsl:template name="footer-metadata">
    <!-- handles: article-categories, kwd-group, counts, 
           supplementary-material, custom-meta-group
         Plus also generates a sheet of processing warnings
         -->
    <xsl:for-each select="front/article-meta | front-stub">
      <xsl:if test="article-categories | counts |
                    supplementary-material | custom-meta-group |
                    custom-meta-wrap">
        <!-- custom-meta-wrap is from NLM 2.3 -->
        <div class="metadata">
            <h2 class="generated-hidden">
              <xsl:text>Article Information (continued)</xsl:text>
            </h2>
            <div class="metadata-group">
              <xsl:apply-templates mode="metadata"
                select="supplementary-material"/>

              <xsl:apply-templates mode="metadata"
                select="article-categories | counts"/>

              <!-- custom-meta carries this tool's internal profile notes.
                   They belong in the archival XML, not in a reader-facing
                   HTML galley, so they are not emitted here. -->
            </div>
      </div>
      </xsl:if>
    </xsl:for-each>

    <xsl:variable name="process-warnings">
      <xsl:call-template name="process-warnings"/>
    </xsl:variable>

    <xsl:if test="normalize-space(string($process-warnings))">
      <hr class="part-rule"/>
      <div class="metadata one-column table">
        <!--<div class="row">
          <div class="cell spanning">
            
          </div>
        </div>-->
        <div class="row">
          <div class="cell spanning">
            <h4 class="generated">
              <xsl:text>Process warnings</xsl:text>
            </h4>
            <p>Warnings reported by the processor due to problematic markup follow:</p>
            <div class="metadata-group">
              <xsl:copy-of select="$process-warnings"/>
            </div>
          </div>
        </div>
      </div>
    </xsl:if>
  </xsl:template>


<!-- ============================================================= -->
<!--  METADATA PROCESSING                                          -->
<!-- ============================================================= -->

<!--  Includes mode "metadata" for front matter, along with 
      "metadata-inline" for metadata elements collapsed into 
      inline sequences, plus associated named templates            -->

  <!-- WAS journal-meta content:
       journal-id+, journal-title-group*, issn+, isbn*, publisher?,
       notes? -->
  <!-- (journal-id+, journal-title-group*, (contrib-group | aff | aff-alternatives)*,
       issn+, issn-l?, isbn*, publisher?, notes*, self-uri*) -->
  <xsl:template match="journal-id" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">
        <xsl:text>Journal ID</xsl:text>
        <xsl:for-each select="@journal-id-type">
          <xsl:text> (</xsl:text>
          <span class="data">
            <xsl:value-of select="."/>
          </span>
          <xsl:text>)</xsl:text>
        </xsl:for-each>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="journal-title-group" mode="metadata">
    <xsl:apply-templates mode="metadata"/>
  </xsl:template>


  <xsl:template match="issn" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">
        <xsl:text>ISSN</xsl:text>
        <xsl:call-template name="append-pub-type"/>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="issn-l" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">
        <xsl:text>ISSN-L</xsl:text>
        <xsl:call-template name="append-pub-type"/>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="isbn" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">
        <xsl:text>ISBN</xsl:text>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="publisher" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">Publisher</xsl:with-param>
      <xsl:with-param name="contents">
        <xsl:apply-templates select="publisher-name" mode="metadata-inline"/>
        <xsl:apply-templates select="publisher-loc" mode="metadata-inline"/>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="publisher-name" mode="metadata-inline">
    <xsl:apply-templates/>
  </xsl:template>


  <xsl:template match="publisher-loc" mode="metadata-inline">
    <span class="generated"> (</span>
    <xsl:apply-templates/>
    <span class="generated">)</span>
  </xsl:template>


  <xsl:template match="notes" mode="metadata">
    <xsl:call-template name="metadata-area">
      <xsl:with-param name="label">Notes</xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <!-- journal-title-group content:
       (journal-title*, journal-subtitle*, trans-title-group*,
       abbrev-journal-title*) -->

  <xsl:template match="journal-title" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">Title</xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="journal-subtitle" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">Subtitle</xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="trans-title-group" mode="metadata">
    <xsl:apply-templates mode="metadata"/>
  </xsl:template>


  <xsl:template match="abbrev-journal-title" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">Abbreviated Title</xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <!-- trans-title-group content: (trans-title, trans-subtitle*) -->

  <xsl:template match="trans-title" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">
        <xsl:text>Translated Title</xsl:text>
        <xsl:for-each select="(../@xml:lang|@xml:lang)[last()]">
          <xsl:text> (</xsl:text>
          <span class="data">
            <xsl:value-of select="."/>
          </span>
          <xsl:text>)</xsl:text>
        </xsl:for-each>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="trans-subtitle" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">
        <xsl:text>Translated Subtitle</xsl:text>
        <xsl:for-each select="(../@xml:lang|@xml:lang)[last()]">
          <xsl:text> (</xsl:text>
          <span class="data">
            <xsl:value-of select="."/>
          </span>
          <xsl:text>)</xsl:text>
        </xsl:for-each>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <!-- article-meta content:
    (article-id*, article-categories?, title-group,
     (contrib-group | aff)*, author-notes?, pub-date+, volume?,
     volume-id*, volume-series?, issue?, issue-id*, 
     issue-title*, issue-sponsor*, issue-part?, isbn*, 
     supplement?, ((fpage, lpage?, page-range?) | elocation-id)?, 
     (email | ext-link | uri | product | supplementary-material)*, 
     history?, permissions?, self-uri*, related-article*,
     abstract*, trans-abstract*, 
     kwd-group*, funding-group*, conference*, counts?, 
     custom-meta-group?) -->

  <!-- In order of appearance... -->

  <xsl:template match="ext-link" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">
        <xsl:text>External link</xsl:text>
        <xsl:for-each select="ext-link-type">
          <xsl:text> (</xsl:text>
          <span class="data">
            <xsl:value-of select="."/>
          </span>
          <xsl:text>)</xsl:text>
        </xsl:for-each>
      </xsl:with-param>
      <xsl:with-param name="contents">
        <xsl:apply-templates select="."/>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="email" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">Email</xsl:with-param>
      <xsl:with-param name="contents">
        <xsl:apply-templates select="."/>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="uri" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">URI</xsl:with-param>
      <xsl:with-param name="contents">
        <xsl:apply-templates select="."/>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="self-uri" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">
        <xsl:text>Self URI</xsl:text>
      </xsl:with-param>
      <xsl:with-param name="contents">
        <a href="{@xlink:href}">
          <xsl:choose>
            <xsl:when test="normalize-space(string(.))">
              <xsl:apply-templates/>
            </xsl:when>
            <xsl:otherwise>
              <xsl:value-of select="@xlink:href"/>
            </xsl:otherwise>
          </xsl:choose>
        </a>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="product" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">
        <xsl:text>Product Information</xsl:text>
      </xsl:with-param>
      <xsl:with-param name="contents">
        <xsl:choose>
          <xsl:when test="normalize-space(string(@xlink:href))">
            <a>
              <xsl:call-template name="assign-href"/>
              <xsl:apply-templates/>
            </a>
          </xsl:when>
          <xsl:otherwise>
            <xsl:apply-templates/>
          </xsl:otherwise>
        </xsl:choose>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="permissions" mode="metadata">
    <xsl:apply-templates select="copyright-statement" mode="metadata"/>
    <xsl:if test="copyright-year | copyright-holder">
      <xsl:call-template name="metadata-labeled-entry">
        <xsl:with-param name="label">Copyright</xsl:with-param>
        <xsl:with-param name="contents">
          <xsl:for-each select="copyright-year | copyright-holder">
            <xsl:apply-templates/>
            <xsl:if test="not(position()=last())">, </xsl:if>
          </xsl:for-each>
        </xsl:with-param>
      </xsl:call-template>
    </xsl:if>
    <xsl:apply-templates select="license" mode="metadata"/>
  </xsl:template>


  <xsl:template match="copyright-statement" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">Copyright statement</xsl:with-param>
    </xsl:call-template>
  </xsl:template>
  
  
  <xsl:template match="copyright-year" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">Copyright</xsl:with-param>
    </xsl:call-template>
  </xsl:template>
  
  
  <xsl:template match="license" mode="metadata">
    <xsl:call-template name="metadata-area">
      <xsl:with-param name="label">
        <xsl:text>License</xsl:text>
        <xsl:if test="@license-type | @xlink:href">
          <xsl:text> (</xsl:text>
          <span class="data">
            <xsl:value-of select="@license-type"/>
            <xsl:if test="@xlink:href">
              <xsl:if test="@license-type">, </xsl:if>
              <a>
                <xsl:call-template name="assign-href"/>
                <xsl:value-of select="@xlink:href"/>
              </a>
            </xsl:if>
          </span>
          <xsl:text>)</xsl:text>
        </xsl:if>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="history/date" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">
        <xsl:text>Date</xsl:text>
        <xsl:for-each select="@date-type">
          <xsl:choose>
            <xsl:when test=".='accepted'"> accepted</xsl:when>
            <xsl:when test=".='received'"> received</xsl:when>
            <xsl:when test=".='rev-request'"> revision requested</xsl:when>
            <xsl:when test=".='rev-recd'"> revision received</xsl:when>
          </xsl:choose>
        </xsl:for-each>
      </xsl:with-param>
      <xsl:with-param name="contents">
        <xsl:call-template name="format-date"/>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="pub-date" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">
        <xsl:text>Publication date</xsl:text>
        <xsl:call-template name="append-pub-type"/>
      </xsl:with-param>
      <xsl:with-param name="contents">
        <xsl:call-template name="format-date"/>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template name="volume-info">
    <!-- handles volume?, volume-id*, volume-series? -->
    <xsl:if test="volume | volume-id | volume-series">
      <xsl:choose>
        <xsl:when test="not(volume-id[2]) or not(volume)">
          <!-- if there are no multiple volume-id, or no volume, we make one line only -->
          <xsl:call-template name="metadata-labeled-entry">
            <xsl:with-param name="label">Volume</xsl:with-param>
            <xsl:with-param name="contents">
              <xsl:apply-templates select="volume | volume-series"
                mode="metadata-inline"/>
              <xsl:apply-templates select="volume-id" mode="metadata-inline"/>
            </xsl:with-param>
          </xsl:call-template>
        </xsl:when>
        <xsl:otherwise>
          <xsl:apply-templates select="volume | volume-id | volume-series"
            mode="metadata"/>
        </xsl:otherwise>
      </xsl:choose>
    </xsl:if>
  </xsl:template>


  <xsl:template match="volume | issue" mode="metadata-inline">
    <xsl:apply-templates/>
  </xsl:template>


  <xsl:template match="volume-id | issue-id" mode="metadata-inline">
    <span class="generated">
      <xsl:text> (</xsl:text>
      <xsl:for-each select="@pub-id-type">
        <span class="data">
          <xsl:value-of select="."/>
        </span>
        <xsl:text> </xsl:text>
      </xsl:for-each>
      <xsl:text>ID: </xsl:text>
    </span>
    <xsl:apply-templates/>
    <span class="generated">)</span>
  </xsl:template>


  <xsl:template match="volume-series" mode="metadata-inline">
    <xsl:if test="preceding-sibling::volume">
      <span class="generated">,</span>
    </xsl:if>
    <xsl:text> </xsl:text>
    <xsl:apply-templates/>
  </xsl:template>


  <xsl:template match="volume" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">Volume</xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="volume-id" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">
        <xsl:text>Volume ID</xsl:text>
        <xsl:for-each select="@pub-id-type">
          <xsl:text> (</xsl:text>
          <span class="data">
            <xsl:value-of select="."/>
          </span>
          <xsl:text>)</xsl:text>
        </xsl:for-each>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="volume-series" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">Series</xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template name="issue-info">
    <!-- handles issue?, issue-id*, issue-title*, issue-sponsor*, issue-part?, supplement? -->
    <xsl:variable name="issue-info"
      select="issue | issue-id | issue-title |
      issue-sponsor | issue-part"/>
    <xsl:choose>
      <xsl:when
        test="$issue-info and not(issue-id[2] | issue-title[2] | issue-sponsor | issue-part)">
        <!-- if there are only one issue, issue-id and issue-title and nothing else, we make one line only -->
        <xsl:call-template name="metadata-labeled-entry">
          <xsl:with-param name="label">Issue</xsl:with-param>
          <xsl:with-param name="contents">
            <xsl:apply-templates select="issue | issue-title"
              mode="metadata-inline"/>
            <xsl:apply-templates select="issue-id" mode="metadata-inline"/>
          </xsl:with-param>
        </xsl:call-template>
      </xsl:when>
      <xsl:otherwise>
        <xsl:apply-templates select="$issue-info" mode="metadata"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>


  <xsl:template match="issue-title" mode="metadata-inline">
    <span class="generated">
      <xsl:if test="preceding-sibling::issue">,</xsl:if>
    </span>
    <xsl:text> </xsl:text>
    <xsl:apply-templates/>
  </xsl:template>


  <xsl:template match="issue" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">Issue</xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="issue-id" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">
        <xsl:text>Issue ID</xsl:text>
        <xsl:for-each select="@pub-id-type">
          <xsl:text> (</xsl:text>
          <span class="data">
            <xsl:value-of select="."/>
          </span>
          <xsl:text>)</xsl:text>
        </xsl:for-each>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="issue-title" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">Issue title</xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="issue-sponsor" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">Issue sponsor</xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="issue-part" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">Issue part</xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template name="page-info">
    <!-- handles (fpage, lpage?, page-range?) -->
    <xsl:if test="fpage | lpage | page-range">
      <xsl:call-template name="metadata-labeled-entry">
        <xsl:with-param name="label">
          <xsl:text>Page</xsl:text>
          <xsl:if
            test="normalize-space(string(lpage[not(.=../fpage)]))
                   or normalize-space(string(page-range))">
            <!-- we have multiple pages if lpage exists and is not equal fpage,
               or if we have a page-range -->
            <xsl:text>s</xsl:text>
          </xsl:if>
        </xsl:with-param>
        <xsl:with-param name="contents">
          <xsl:value-of select="fpage"/>
          <xsl:if test="normalize-space(string(lpage[not(.=../fpage)]))">
            <xsl:text>-</xsl:text>
            <xsl:value-of select="lpage"/>
          </xsl:if>
          <xsl:for-each select="page-range">
            <xsl:text> (pp. </xsl:text>
            <xsl:value-of select="."/>
            <xsl:text>)</xsl:text>
          </xsl:for-each>
        </xsl:with-param>
      </xsl:call-template>
    </xsl:if>
  </xsl:template>


  <xsl:template match="elocation-id" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">Electronic Location
      Identifier</xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <!-- isbn is already matched in mode 'metadata' above -->

  <xsl:template match="supplement" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">Supplement Info</xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="related-article | related-object" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">
        <xsl:text>Related </xsl:text>
          <xsl:choose>
            <xsl:when test="self::related-object">object</xsl:when>
            <xsl:otherwise>article</xsl:otherwise>
          </xsl:choose>
        <xsl:for-each select="@related-article-type | @object-type">
          <xsl:text> (</xsl:text>
          <span class="data">
            <xsl:value-of select="translate(.,'-',' ')"/>
          </span>
          <xsl:text>)</xsl:text>
        </xsl:for-each>
      </xsl:with-param>
      <xsl:with-param name="contents">
        <xsl:choose>
          <xsl:when test="normalize-space(string(@xlink:href))">
            <a>
              <xsl:call-template name="assign-href"/>
              <xsl:apply-templates/>
            </a>
          </xsl:when>
          <xsl:otherwise>
            <xsl:apply-templates/>
          </xsl:otherwise>
        </xsl:choose>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="conference" mode="metadata">
    <!-- content model:
      (conf-date, 
       (conf-name | conf-acronym)+, 
       conf-num?, conf-loc?, conf-sponsor*, conf-theme?) -->
    <xsl:choose>
      <xsl:when
        test="not(conf-name[2] | conf-acronym[2] | conf-sponsor |
                  conf-theme)">
        <!-- if there is no second name or acronym, and no sponsor
             or theme, we make one line only -->
        <xsl:call-template name="metadata-labeled-entry">
          <xsl:with-param name="label">Conference</xsl:with-param>
          <xsl:with-param name="contents">
            <xsl:apply-templates select="conf-acronym | conf-name"
              mode="metadata-inline"/>
            <xsl:apply-templates select="conf-num" mode="metadata-inline"/>
            <xsl:if test="conf-date | conf-loc">
              <span class="generated"> (</span>
              <xsl:for-each select="conf-date | conf-loc">
                <xsl:if test="position() = 2">, </xsl:if>
                <xsl:apply-templates select="." mode="metadata-inline"/>
              </xsl:for-each>
              <span class="generated">)</span>
            </xsl:if>
          </xsl:with-param>
        </xsl:call-template>
      </xsl:when>
      <xsl:otherwise>
        <xsl:apply-templates mode="metadata"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>


  <xsl:template match="conf-date" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">Conference date</xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="conf-name" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">Conference</xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="conf-acronym" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">Conference</xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="conf-num" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">Conference number</xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="conf-loc" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">Conference location</xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="conf-sponsor" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">Conference sponsor</xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="conf-theme" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">Conference theme</xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="conf-name | conf-acronym" mode="metadata-inline">
    <!-- we only hit this template if there is at most one of each -->
    <xsl:variable name="following"
      select="preceding-sibling::conf-name | preceding-sibling::conf-acronym"/>
    <!-- if we come after the other, we go in parentheses -->
    <xsl:if test="$following">
      <span class="generated"> (</span>
    </xsl:if>
    <xsl:apply-templates/>
    <xsl:if test="$following">
      <span class="generated">)</span>
    </xsl:if>
  </xsl:template>


  <xsl:template match="conf-num" mode="metadata-inline">
    <xsl:text> </xsl:text>
    <xsl:apply-templates/>
  </xsl:template>


  <xsl:template match="conf-date | conf-loc" mode="metadata-inline">
    <xsl:apply-templates/>
  </xsl:template>


  <xsl:template match="article-id" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">
        <xsl:choose>
          <xsl:when test="@pub-id-type='art-access-id'">Accession ID</xsl:when>
          <xsl:when test="@pub-id-type='coden'">Coden</xsl:when>
          <xsl:when test="@pub-id-type='doi'">DOI</xsl:when>
          <xsl:when test="@pub-id-type='manuscript'">Manuscript ID</xsl:when>
          <xsl:when test="@pub-id-type='medline'">Medline ID</xsl:when>
          <xsl:when test="@pub-id-type='pii'">Publisher Item ID</xsl:when>
          <xsl:when test="@pub-id-type='pmid'">PubMed ID</xsl:when>
          <xsl:when test="@pub-id-type='publisher-id'">Publisher ID</xsl:when>
          <xsl:when test="@pub-id-type='sici'">Serial Item and Contribution ID</xsl:when>
          <xsl:when test="@pub-id-type='doaj'">DOAJ ID</xsl:when>
          <xsl:when test="@pub-id-type='arXiv'">arXiv.org ID</xsl:when>
          <xsl:otherwise>
            <xsl:text>Article Id</xsl:text>
            <xsl:for-each select="@pub-id-type">
              <xsl:text> (</xsl:text>
              <span class="data">
                <xsl:value-of select="."/>
              </span>
              <xsl:text>)</xsl:text>
            </xsl:for-each>
          </xsl:otherwise>
        </xsl:choose>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="contract-num" mode="metadata">
    <!-- only in 2.3 -->
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">Contract</xsl:with-param>
    </xsl:call-template>
  </xsl:template>
  
  <xsl:template match="contract-sponsor" mode="metadata">
    <!-- only in 2.3 -->
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">Contract Sponsor</xsl:with-param>
    </xsl:call-template>
  </xsl:template>
  
  <xsl:template match="grant-num" mode="metadata">
    <!-- only in 2.3 -->
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">Grant Number</xsl:with-param>
    </xsl:call-template>
  </xsl:template>
  
  <xsl:template match="grant-sponsor" mode="metadata">
    <!-- only in 2.3 -->
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">Grant Sponsor</xsl:with-param>
    </xsl:call-template>
  </xsl:template>
  
  
  <xsl:template match="award-group" mode="metadata">
    <!-- includes (funding-source*, award-id*, principal-award-recipient*, principal-investigator*) -->
    <xsl:apply-templates mode="metadata"/>
  </xsl:template>


  <xsl:template match="funding-source" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">Funded by</xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="award-id" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">Award ID</xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="principal-award-recipient" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">Award Recipient</xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="principal-investigator" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">Principal Investigator</xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="funding-statement" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">Funding</xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="open-access" mode="metadata">
    <xsl:call-template name="metadata-area">
      <xsl:with-param name="label">Open Access</xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <!-- The coloured section label above the title ("BOOK REVIEW",
       "ARTICLE", ...), in the colours the BC Studies website uses for the
       same section. The class is the subject in lower case with spaces as
       hyphens and commas/ampersands dropped: "BOOK REVIEW" ->
       section-tag-book-review. Context: article-meta or front-stub. -->
  <xsl:template name="section-tag">
    <xsl:variable name="subject"
      select="normalize-space(string(article-categories/subj-group[@subj-group-type='heading'][1]/subject[1]))"/>
    <xsl:if test="$subject">
      <p class="section-tag section-tag-{translate($subject,
          'ABCDEFGHIJKLMNOPQRSTUVWXYZ ,&amp;',
          'abcdefghijklmnopqrstuvwxyz-')}">
        <xsl:choose>
          <!-- the JATS subject stays the full section name; the label on
               the page is just "Bibliography" -->
          <xsl:when test="$subject = 'BIBLIOGRAPHY OF BRITISH COLUMBIA'">BIBLIOGRAPHY</xsl:when>
          <xsl:otherwise><xsl:value-of select="$subject"/></xsl:otherwise>
        </xsl:choose>
      </p>
    </xsl:if>
  </xsl:template>


  <xsl:template match="title-group" mode="metadata">
    <!-- content model:
    article-title, subtitle*, trans-title-group*, alt-title*, fn-group? -->
    <!-- A review is headed with its short title; the full title of the book
         is printed in the book-info box at the top of the body. Review
         essays keep their own title. -->
    <xsl:variable name="short"
      select="alt-title[@alt-title-type='running-head'][normalize-space()][1]"/>
    <xsl:variable name="review-heading"
      select="$short and ancestor::article[1]/@article-type = 'book-review'
              and not(../article-categories//subject = 'REVIEW ESSAY')"/>
    <xsl:choose>
      <xsl:when test="$review-heading">
        <h1 class="document-title">
          <xsl:apply-templates select="$short/node()"/>
        </h1>
        <xsl:apply-templates select="trans-title-group | trans-title |
          trans-subtitle" mode="metadata"/>
      </xsl:when>
      <xsl:otherwise>
        <!-- trans-title and trans-subtitle included for 2.3 -->
        <xsl:apply-templates select="article-title | subtitle | trans-title-group |
          trans-title | trans-subtitle"
          mode="metadata"/>
      </xsl:otherwise>
    </xsl:choose>
    <xsl:variable name="notes"
      select="alt-title[not($review-heading and count(. | $short) = 1)] | fn-group"/>
    <xsl:if test="$notes">
      <div class="document-title-notes metadata-group">
        <xsl:apply-templates select="$notes" mode="metadata"/>
      </div>
    </xsl:if>
  </xsl:template>


  <xsl:template match="title-group/article-title" mode="metadata">
    <h1 class="document-title">
      <xsl:apply-templates/>
      <!-- the subtitle gets its own line, so no colon is generated here -->
    </h1>
  </xsl:template>


  <xsl:template match="title-group/subtitle | trans-title-group/subtitle"
    mode="metadata">
    <p class="document-subtitle" role="doc-subtitle">
      <xsl:apply-templates/>
    </p>
  </xsl:template>


  <!-- "BC Studies, no. 226 (Summer 2025): 31-52. DOI: https://doi.org/..."
       Context: article-meta or front-stub. UNKNOWN placeholders from an
       unfinished draft are never printed. -->
  <xsl:template name="journal-line">
    <xsl:variable name="jtitle">
      <xsl:choose>
        <xsl:when test="normalize-space(string(ancestor::front/journal-meta//abbrev-journal-title[1]))">
          <xsl:value-of select="normalize-space(string(ancestor::front/journal-meta//abbrev-journal-title[1]))"/>
        </xsl:when>
        <xsl:otherwise>
          <xsl:value-of select="normalize-space(string(ancestor::front/journal-meta//journal-title[1]))"/>
        </xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    <xsl:variable name="doi" select="article-id[@pub-id-type='doi'][1]"/>
    <!-- Guarded like cite-year: a union with [1] would return the epub
         date (first in document order), which has no season. -->
    <xsl:variable name="collection" select="pub-date[@pub-type='collection'][1]"/>
    <xsl:variable name="ppub" select="pub-date[@pub-type='ppub'][1]"/>
    <xsl:variable name="date"
      select="$collection
              | $ppub[not($collection)]
              | pub-date[1][not($collection) and not($ppub)]"/>
    <xsl:variable name="has-issue"
      select="normalize-space(string(issue)) and not(issue = 'UNKNOWN')"/>
    <xsl:if test="string($jtitle) or $has-issue or normalize-space(string($doi))">
      <p class="journal-line">
        <xsl:if test="string($jtitle)">
          <cite class="journal-name"><xsl:value-of select="$jtitle"/></cite>
        </xsl:if>
        <xsl:if test="$has-issue">
          <xsl:if test="string($jtitle)">,</xsl:if>
          <xsl:text> no. </xsl:text>
          <xsl:value-of select="normalize-space(string(issue))"/>
        </xsl:if>
        <xsl:if test="normalize-space(string($date/year)) and not($date/year = 'UNKNOWN')">
          <xsl:text> (</xsl:text>
          <xsl:if test="normalize-space(string($date/season))">
            <xsl:value-of select="normalize-space(string($date/season))"/>
            <xsl:text> </xsl:text>
          </xsl:if>
          <xsl:value-of select="normalize-space(string($date/year))"/>
          <xsl:text>)</xsl:text>
        </xsl:if>
        <xsl:if test="normalize-space(string(fpage))">
          <xsl:text>: </xsl:text>
          <xsl:value-of select="normalize-space(string(fpage))"/>
          <xsl:if test="normalize-space(string(lpage)) and not(lpage = fpage)">
            <xsl:text>&#8211;</xsl:text>
            <xsl:value-of select="normalize-space(string(lpage))"/>
          </xsl:if>
        </xsl:if>
        <xsl:if test="string($jtitle) or $has-issue">
          <xsl:text>.</xsl:text>
        </xsl:if>
        <xsl:if test="normalize-space(string($doi))">
          <xsl:text> DOI: </xsl:text>
          <a class="doi-link" href="{concat('https://doi.org/', normalize-space(string($doi)))}"
             target="_blank" rel="noopener noreferrer">
            <xsl:text>https://doi.org/</xsl:text>
            <xsl:value-of select="normalize-space(string($doi))"/>
            <span class="visually-hidden"> (opens in a new tab)</span>
          </a>
        </xsl:if>
      </p>
    </xsl:if>
  </xsl:template>


  <xsl:template match="title-group/trans-title-group" mode="metadata">
    <!-- content model: (trans-title, trans-subtitle*) -->
    <xsl:apply-templates mode="metadata"/>
  </xsl:template>



  <xsl:template match="title-group/alt-title" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">
        <xsl:text>Alternative title</xsl:text>
        <xsl:for-each select="@alt-title-type">
          <xsl:text> (</xsl:text>
          <span class="data">
            <xsl:value-of select="."/>
          </span>
          <xsl:text>)</xsl:text>
        </xsl:for-each>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="title-group/fn-group" mode="metadata">
    <xsl:apply-templates/>
  </xsl:template>

  

  <xsl:template mode="metadata" match="journal-meta/contrib-group">
    <xsl:for-each select="contrib">
      <xsl:variable name="contrib-identification">
        <xsl:call-template name="contrib-identify"/>
      </xsl:variable>
      <!-- placing the div only if it has content -->
      <!-- the extra call to string() makes it type-safe in a type-aware
           XSLT 2.0 engine -->
      <xsl:if test="normalize-space(string($contrib-identification))">
        <xsl:copy-of select="$contrib-identification"/>
      </xsl:if>
      <xsl:variable name="contrib-info">
        <xsl:call-template name="contrib-info"/>
      </xsl:variable>
      <!-- placing the div only if it has content -->
      <xsl:if test="normalize-space(string($contrib-info))">
        <xsl:copy-of select="$contrib-info"/>
      </xsl:if>
    </xsl:for-each>
    
    <xsl:if test="*[not(self::contrib | self::xref)]">
      
        <xsl:apply-templates mode="metadata"
          select="*[not(self::contrib | self::xref)]"/>
      
    </xsl:if>
  </xsl:template>
  
  <xsl:template mode="metadata" match="article-meta/contrib-group">
    <div class="author-list">
      <p class="authors">
        <xsl:if test="@content-type = 'editor'">
          <xsl:attribute name="class">authors editors</xsl:attribute>
          <span class="editor-role">
            <xsl:choose>
              <xsl:when test="count(contrib) &gt; 1">Editors: </xsl:when>
              <xsl:otherwise>Editor: </xsl:otherwise>
            </xsl:choose>
          </span>
        </xsl:if>
        <xsl:variable name="is-editor" select="@content-type = 'editor'"/>
        <!-- "Reviewed by Jane Smith" on reviews; review essays have authors -->
        <xsl:variable name="is-review"
          select="not($is-editor) and ancestor::article[1]/@article-type = 'book-review'
                  and not(../article-categories//subject = 'REVIEW ESSAY')"/>
        <xsl:for-each select="contrib">
          <xsl:choose>
            <!-- Editors stay on one line: "Editors: A, B, and C" -->
            <xsl:when test="$is-editor">
              <!-- Separator logic for second item and onwards -->
              <xsl:if test="position() > 1">
                <xsl:choose>
                  <!-- When there are more than 2 editors in total -->
                  <xsl:when test="last() > 2">
                    <xsl:choose>
                      <xsl:when test="position() = last()">, and </xsl:when>
                      <xsl:otherwise>, </xsl:otherwise>
                    </xsl:choose>
                  </xsl:when>
                  <!-- When there are exactly 2 editors in total -->
                  <xsl:otherwise> and </xsl:otherwise>
                </xsl:choose>
              </xsl:if>
              <span class="author-name">
                <xsl:call-template name="contrib-identify"/>
              </span>
              <xsl:apply-templates select="contrib-id[@contrib-id-type='orcid']" mode="orcid-link"/>
            </xsl:when>
            <!-- Authors: one per line, each with its own ORCID link -->
            <xsl:otherwise>
              <span class="author-entry">
                <xsl:if test="$is-review and position() = 1">
                  <span class="byline-role">Reviewed by </span>
                </xsl:if>
                <!-- the Bibliography of British Columbia: "Prepared by David
                     Gill, MLIS" -->
                <xsl:if test="role[@content-type = 'compiler'] and position() = 1">
                  <span class="byline-role"><xsl:value-of select="normalize-space(role[@content-type = 'compiler'])"/><xsl:text> </xsl:text></span>
                </xsl:if>
                <span class="author-name">
                  <xsl:call-template name="contrib-identify"/>
                </span>
<!-- (the degree, "MLIS", is printed by contrib-identify) -->
                <xsl:apply-templates select="contrib-id[@contrib-id-type='orcid']" mode="orcid-link"/>
              </span>
            </xsl:otherwise>
          </xsl:choose>
        </xsl:for-each>
      </p>
    </div>
  </xsl:template>


  <!-- ORCID iD: the green icon linking to the record, right after the name -->
  <xsl:template match="contrib-id" mode="orcid-link">
    <xsl:variable name="raw" select="normalize-space(string(.))"/>
    <xsl:variable name="href">
      <xsl:choose>
        <xsl:when test="starts-with($raw, 'http')"><xsl:value-of select="$raw"/></xsl:when>
        <xsl:otherwise><xsl:value-of select="concat('https://orcid.org/', $raw)"/></xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    <xsl:text> </xsl:text>
    <a class="orcid-link" href="{$href}" target="_blank" rel="noopener noreferrer">
      <svg class="orcid-icon" viewBox="0 0 256 256" width="16" height="16" aria-hidden="true" focusable="false">
        <path fill="#A6CE39" d="M256 128c0 70.7-57.3 128-128 128S0 198.7 0 128 57.3 0 128 0s128 57.3 128 128z"/>
        <path fill="#FFF" d="M86.3 186.2H70.9V79.1h15.4v107.1zM108.9 79.1h41.6c39.6 0 57 28.3 57 53.6 0 27.5-21.5 53.6-56.8 53.6h-41.8V79.1zm15.4 93.3h24.5c34.9 0 42.9-26.5 42.9-39.7 0-21.5-13.7-39.7-43.7-39.7h-23.7v79.4zM88.7 56.8c0 5.5-4.5 10.1-10.1 10.1s-10.1-4.6-10.1-10.1c0-5.6 4.5-10.1 10.1-10.1s10.1 4.6 10.1 10.1z"/>
      </svg>
      <span class="orcid-text"><xsl:value-of select="$href"/></span>
      <span class="visually-hidden"> (ORCID record, opens in a new tab)</span>
    </a>
  </xsl:template>
  
  
  <xsl:template name="contrib-identify">
    <xsl:for-each select="anonymous | collab | collab-alternatives/* | name | name-alternatives/*">
      <xsl:apply-templates select="." mode="metadata-inline"/>
      <xsl:if test="position() != last()"> </xsl:if>
    </xsl:for-each>
    <xsl:apply-templates select="degrees | xref" mode="metadata-inline"/>
  </xsl:template>


  <xsl:template match="anonymous" mode="metadata-inline">
    <xsl:text>Anonymous</xsl:text>        
  </xsl:template>


  <xsl:template match="collab |
                       collab-alternatives/*" mode="metadata-inline">
    <xsl:apply-templates/>
  </xsl:template>


  <xsl:template match="contrib/name |
                       contrib/name-alternatives/*" mode="metadata-inline">
    <xsl:apply-templates select="."/>
  </xsl:template>


  <xsl:template match="degrees" mode="metadata-inline">
    <xsl:text>, </xsl:text>
    <xsl:apply-templates/>
  </xsl:template>


  <xsl:template match="xref" mode="metadata-inline">
    <!-- These are not expected to appear in mixed content, so
      brackets are provided -->
    <span class="generated">[</span>
    <xsl:apply-templates select="."/>
    <span class="generated">]</span>
  </xsl:template>
  
  <xsl:template match="contrib-id" mode="metadata-inline">
    <!-- ORCIDs are rendered as an icon link beside the name (mode orcid-link);
         any other identifier type is not shown in the byline. -->
  </xsl:template>
  
  
  <xsl:template name="contrib-info">
    <!-- Placed in a right-hand pane -->
    <div class="metadata-group">
      <xsl:apply-templates mode="metadata"
        select="address | aff | author-comment | email |
                ext-link | on-behalf-of | role | uri"/>
    </div>
  </xsl:template>


  <xsl:template mode="metadata"
    match="address[not(addr-line) or not(*[2])]">
    <!-- when we have no addr-line or a single child, we generate
         a single unlabelled line -->
        <xsl:call-template name="metadata-entry">
          <xsl:with-param name="contents">
            <xsl:call-template name="address-line"/>
          </xsl:with-param>
        </xsl:call-template>
  </xsl:template>


  <xsl:template match="address" mode="metadata">
    <!-- when we have an addr-line we generate an unlabelled block -->
    <xsl:call-template name="metadata-area">
      <xsl:with-param name="contents">
        <xsl:apply-templates mode="metadata"/>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template mode="metadata" priority="2" match="address/*">
    <!-- being sure to override other templates for these
         element types -->
    <xsl:call-template name="metadata-entry"/>
  </xsl:template>


  <xsl:template match="aff" mode="metadata">
    <xsl:call-template name="metadata-entry">
      <xsl:with-param name="contents">
        <xsl:call-template name="named-anchor"/>
        <xsl:apply-templates/>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="author-comment" mode="metadata">
    <xsl:call-template name="metadata-area">
      <xsl:with-param name="label">Comment</xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="bio" mode="metadata">
    <xsl:call-template name="metadata-area">
      <xsl:with-param name="label">Bio</xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="on-behalf-of" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">On behalf of</xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="role" mode="metadata">
    <xsl:call-template name="metadata-entry"/>
  </xsl:template>


  <xsl:template match="author-notes" mode="metadata">
    <xsl:call-template name="metadata-area">
      <xsl:with-param name="label">Author notes</xsl:with-param>
      <xsl:with-param name="contents">
        <xsl:call-template name="named-anchor"/>
        <xsl:apply-templates mode="metadata"/>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="author-notes/corresp" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">
        <xsl:call-template name="named-anchor"/>
        <xsl:text>Correspondence to</xsl:text>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="author-notes/fn | author-notes/p" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">
        <xsl:apply-templates select="@fn-type"/>
      </xsl:with-param>
      <xsl:with-param name="contents">
        <xsl:call-template name="named-anchor"/>
        <xsl:apply-templates/>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>

  
  <xsl:template match="supplementary-material" mode="metadata">
    <xsl:call-template name="metadata-area">
      <xsl:with-param name="label">Supplementary material</xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="article-categories" mode="metadata">
    <xsl:apply-templates mode="metadata"/>
  </xsl:template>


  <xsl:template match="article-categories/subj-group" mode="metadata">
    <xsl:call-template name="metadata-area">
      <xsl:with-param name="label">Categories</xsl:with-param>
      <xsl:with-param name="contents">
        <xsl:apply-templates mode="metadata"/>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="subj-group" mode="metadata">
    <xsl:apply-templates mode="metadata"/>
  </xsl:template>


  <xsl:template match="subj-group/subj-group" mode="metadata">
    <div class="metadata-area">
      <xsl:apply-templates mode="metadata"/>
    </div>
  </xsl:template>


  <xsl:template match="subj-group/subject" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">Subject</xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="series-title" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">Series title</xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="series-text" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">Series description</xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="kwd-group" mode="metadata">
    <div class="metadata-area">
      <div class="metadata-chunk">
        <xsl:if test="title|label">
          <span class="generated">
            <xsl:apply-templates select="title|label" mode="metadata-inline"/>
            <xsl:text>: </xsl:text>
          </span>
        </xsl:if>
        <xsl:if test="not(title|label)">
          <span class="generated">Keywords: </span>
        </xsl:if>
        <xsl:for-each select="kwd | nested-kwd//kwd | compound-kwd/compound-kwd-part">
          <xsl:if test="position() &gt; 1">
            <xsl:text>, </xsl:text>
          </xsl:if>
          <xsl:apply-templates select="."/>
        </xsl:for-each>
      </div>
    </div>
  </xsl:template>


  <xsl:template match="title" mode="metadata">
    <xsl:apply-templates select="."/>
  </xsl:template>


  <xsl:template match="kwd" mode="metadata">
    <xsl:apply-templates/>
  </xsl:template>

  <xsl:template match="nested-kwd" mode="metadata">
    <ul class="nested-kwd">
      <xsl:apply-templates mode="metadata"/>
    </ul>
  </xsl:template>
  
  <xsl:template match="nested-kwd/kwd" mode="metadata">
    <li class="kwd">
      <xsl:apply-templates/>
    </li>
  </xsl:template>
  
  
  <xsl:template match="compound-kwd" mode="metadata">
    <xsl:call-template name="metadata-area">
      <xsl:with-param name="label">Compound keyword</xsl:with-param>
      <xsl:with-param name="contents">
        <xsl:apply-templates mode="metadata"/>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="compound-kwd-part" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">
        <xsl:text>Keyword part</xsl:text>
        <xsl:for-each select="@content-type">
          <xsl:text> (</xsl:text>
          <span class="data">
            <xsl:value-of select="."/>
          </span>
          <xsl:text>)</xsl:text>
        </xsl:for-each>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="counts" mode="metadata">
    <!-- fig-count?, table-count?, equation-count?, ref-count?,
         page-count?, word-count? -->
    <xsl:call-template name="metadata-area">
      <xsl:with-param name="label">Counts</xsl:with-param>
      <xsl:with-param name="contents">
        <xsl:apply-templates mode="metadata"/>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template mode="metadata"
    match="count | fig-count | table-count | equation-count |
           ref-count | page-count | word-count">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">
        <xsl:apply-templates select="." mode="metadata-label"/>
      </xsl:with-param>
      <xsl:with-param name="contents">
        <xsl:value-of select="@count"/>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="count"
    mode="metadata-label">
    <xsl:text>Count</xsl:text>
    <xsl:for-each select="@count-type">
      <xsl:text> (</xsl:text>
      <span class="data">
        <xsl:value-of select="."/>
      </span>
      <xsl:text>)</xsl:text>
    </xsl:for-each>
  </xsl:template>
  
  
  <xsl:template match="fig-count"
    mode="metadata-label">Figures</xsl:template>
  
  
  <xsl:template match="table-count"
    mode="metadata-label">Tables</xsl:template>


  <xsl:template match="equation-count"
    mode="metadata-label">Equations</xsl:template>


  <xsl:template match="ref-count"
    mode="metadata-label">References</xsl:template>


  <xsl:template match="page-count"
    mode="metadata-label">Pages</xsl:template>


  <xsl:template match="word-count"
    mode="metadata-label">Words</xsl:template>


  <xsl:template mode="metadata"
    match="custom-meta-group | custom-meta-wrap">
    <xsl:call-template name="metadata-area">
      <xsl:with-param name="label">Custom metadata</xsl:with-param>
      <xsl:with-param name="contents">
        <xsl:apply-templates mode="metadata"/>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="custom-meta" mode="metadata">
    <xsl:call-template name="metadata-labeled-entry">
      <xsl:with-param name="label">
        <span class="data">
          <xsl:apply-templates select="meta-name" mode="metadata-inline"/>
        </span>
      </xsl:with-param>
      <xsl:with-param name="contents">
        <xsl:apply-templates select="meta-value" mode="metadata-inline"/>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="meta-name | meta-value" mode="metadata-inline">
    <xsl:apply-templates/>
  </xsl:template>


  <!-- ============================================================= -->
  <!--  REGULAR (DEFAULT) MODE                                       -->
  <!-- ============================================================= -->


  <xsl:template match="sec">
    <div class="section">
      <xsl:call-template name="named-anchor"/>
      <xsl:apply-templates select="title"/>
      <xsl:apply-templates select="sec-meta"/>
      <xsl:apply-templates mode="drop-title"/>
    </div>
  </xsl:template>


  <xsl:template match="*" mode="drop-title">
    <xsl:apply-templates select="."/>
  </xsl:template>


  <xsl:template match="title | sec-meta" mode="drop-title"/>


  <xsl:template match="app">
    <div class="section app">
      <xsl:call-template name="named-anchor"/>
      <xsl:apply-templates select="." mode="label"/>
      <xsl:apply-templates/>
    </div>
  </xsl:template>
  
  
  <xsl:template match="ref-list" name="ref-list">
    <div class="section ref-list">
      <!-- back/ref-list is already wrapped by backmatter-section, which has
           emitted the named anchor for this same node. Emitting it twice
           produced a duplicate id (invalid HTML, ambiguous fragment links). -->
      <xsl:if test="not(parent::back)">
        <xsl:call-template name="named-anchor"/>
      </xsl:if>
      <xsl:apply-templates select="." mode="label"/>
      <xsl:apply-templates select="*[not(self::ref | self::ref-list)]"/>
      <xsl:if test="ref">
        <!-- Each <ref> renders as an <li>, so the container must be a real
             list element. A <div> parent is invalid HTML and costs screen
             readers the "list of N items" announcement. -->
        <ul class="ref-list-items">
          <xsl:apply-templates select="ref"/>
        </ul>
      </xsl:if>
      <xsl:apply-templates select="ref-list"/>
    </div>
  </xsl:template>
  
  
  <xsl:template match="sec-meta">
   <div class="section-metadata">
     <!-- includes contrib-group | permissions | kwd-group -->
     <xsl:apply-templates/>
   </div>
  </xsl:template>


  <xsl:template match="sec-meta/contrib-group">
    <xsl:apply-templates mode="metadata"/>
  </xsl:template>


  <xsl:template match="sec-meta/kwd-group">
    <!-- matches only if contrib-group has only contrib children -->
    <xsl:apply-templates  select="." mode="metadata"/>
  </xsl:template>



  <!-- ============================================================= -->
  <!--  Titles                                                       -->
  <!-- ============================================================= -->

  <xsl:template name="main-title"
    match="abstract/title | body/*/title |
           back/title | back[not(title)]/*/title">
    <xsl:param name="contents">
      <xsl:apply-templates/>
    </xsl:param>
    <xsl:if test="normalize-space(string($contents))">
      <!-- coding defensively since empty titles make glitchy HTML -->
      <h2 class="main-title">
        <xsl:copy-of select="$contents"/>
      </h2>
    </xsl:if>
  </xsl:template>


  <xsl:template name="section-title"
    match="abstract/*/title | body/*/*/title |
		       back[title]/*/title | back[not(title)]/*/*/title">
    <xsl:param name="contents">
      <xsl:apply-templates/>
    </xsl:param>   
    <xsl:if test="normalize-space(string($contents))">
      <!-- coding defensively since empty titles make glitchy HTML -->
      <h3 class="section-title">
        <xsl:copy-of select="$contents"/>
      </h3>
    </xsl:if>
  </xsl:template>


  <xsl:template name="subsection-title"
    match="abstract/*/*/title | body/*/*/*/title |
		       back[title]/*/*/title | back[not(title)]/*/*/*/title">
    <xsl:param name="contents">
      <xsl:apply-templates/>
    </xsl:param>   
    <xsl:if test="normalize-space(string($contents))">
      <!-- coding defensively since empty titles make glitchy HTML -->
      <h4 class="subsection-title">
        <xsl:copy-of select="$contents"/>
      </h4>
    </xsl:if>
  </xsl:template>


  <xsl:template name="block-title" priority="2"
    match="list/title | def-list/title | boxed-text/title |
           verse-group/title | glossary/title | gloss-group/title | kwd-group/title">
    <xsl:param name="contents">
      <xsl:apply-templates/>
    </xsl:param>   
    <xsl:if test="normalize-space(string($contents))">
      <!-- coding defensively since empty titles make glitchy HTML -->
      <h4 class="block-title">
        <xsl:copy-of select="$contents"/>
      </h4>
    </xsl:if>
  </xsl:template>


  <!-- default: any other titles found -->
  <xsl:template match="title">
    <xsl:if test="normalize-space(string(.))">
      <h3 class="title">
        <xsl:apply-templates/>
      </h3>
    </xsl:if>
  </xsl:template>


  <xsl:template match="subtitle">
    <xsl:if test="normalize-space(string(.))">
      <h5 class="subtitle">
        <xsl:apply-templates/>
      </h5>
    </xsl:if>
  </xsl:template>


<!-- ============================================================= -->
<!--  Figures, lists and block-level objectS                       -->
<!-- ============================================================= -->
  
  
  <xsl:template match="address">
    <xsl:choose>
      <!-- address appears as a sequence of inline elements if
           it has no addr-line and the parent may contain text -->
      <xsl:when test="not(addr-line) and
        (parent::collab | parent::p | parent::license-p |
         parent::named-content | parent::styled-content)">
        <xsl:call-template name="address-line"/>
      </xsl:when>
      <xsl:otherwise>
        <div class="address">
          <xsl:apply-templates/>
        </div>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>


  <xsl:template name="address-line">
    <!-- emits element children in a simple comma-delimited sequence -->
    <xsl:for-each select="*">
      <xsl:if test="position() &gt; 1">, </xsl:if>
      <xsl:apply-templates/>
    </xsl:for-each>
  </xsl:template>


  <xsl:template match="address/*">
    <p class="address-line">
      <xsl:apply-templates/>
    </p>
  </xsl:template>
  
  <xsl:template match="array | disp-formula-group | fig-group |
    fn-group | license | long-desc | open-access | sig-block | 
    table-wrap-foot | table-wrap-group">
    <div class="{local-name()}">
      <xsl:apply-templates/>
    </div>
  </xsl:template>
  
  <xsl:template match="attrib">
    <p class="attrib">
      <xsl:apply-templates/>
    </p>
  </xsl:template>


  <xsl:template match="boxed-text | chem-struct-wrap | fig |
                       table-wrap | chem-struct-wrapper">
    <!-- chem-struct-wrapper is from NLM 2.3 -->
    <xsl:variable name="gi">
      <xsl:choose>
        <xsl:when test="self::chem-struct-wrapper">chem-struct-wrap</xsl:when>
        <xsl:otherwise>
          <xsl:value-of select="local-name(.)"/>
        </xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    <!-- fig becomes a semantic <figure>; everything else stays a div -->
    <xsl:variable name="wrapper">
      <xsl:choose>
        <xsl:when test="$gi = 'fig'">figure</xsl:when>
        <xsl:otherwise>div</xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    <xsl:element name="{$wrapper}">
      <xsl:attribute name="class">
        <xsl:value-of select="concat($gi, ' panel')"/>
      </xsl:attribute>
      <!-- boxed-text/@content-type (e.g. "book-info" on reviews) rides
           along as a class so the stylesheet can tell the boxes apart -->
      <xsl:if test="self::boxed-text and normalize-space(@content-type)">
        <xsl:attribute name="class">
          <xsl:value-of select="concat($gi, ' panel ', normalize-space(@content-type))"/>
        </xsl:attribute>
      </xsl:if>
      <xsl:if test="not(@position != 'float')">
        <!-- the test respects @position='float' as the default -->
        <!-- "display: float" is not a CSS value (upstream jats-html.xsl bug);
             the intent is simply to clear preceding floats. -->
        <xsl:attribute name="style">clear: both</xsl:attribute>
      </xsl:if>
      <xsl:call-template name="named-anchor"/>
      <xsl:apply-templates select="." mode="label"/>
      <!-- A <figcaption> must be the first or last child of its <figure>,
           but JATS puts the caption before the graphic. Hold a fig's
           caption back and emit it last, after the image. -->
      <xsl:apply-templates select="node()[not(self::caption and parent::fig)]"/>
      <xsl:apply-templates select="self::fig/caption"/>
      <xsl:apply-templates mode="footnote"
        select="self::table-wrap//fn[not(ancestor::table-wrap-foot)]"/>
    </xsl:element>
  </xsl:template>
  

  <xsl:template match="caption">
    <div class="caption">
      <xsl:apply-templates/>
    </div>
  </xsl:template>

  <!-- a figure's caption is a real <figcaption>, so screen readers
       announce the image and its caption as one figure -->
  <xsl:template match="fig/caption">
    <figcaption class="caption">
      <xsl:apply-templates/>
    </figcaption>
  </xsl:template>
  

  <xsl:template match="disp-formula | statement">
    <div class="{local-name()} panel">
      <xsl:call-template name="named-anchor"/>
      <xsl:apply-templates select="." mode="label"/>
      <xsl:apply-templates/>
    </div>
  </xsl:template>
  

  <xsl:template match="glossary | gloss-group">
    <!-- gloss-group is from 2.3 -->
    <div class="glossary">
      <xsl:call-template name="named-anchor"/>
      <xsl:apply-templates select="label | title"/>
      <xsl:if test="not(normalize-space(string(title)))">
        <xsl:call-template name="block-title">
          <xsl:with-param name="contents">
            <span class="generated">Glossary</span>
          </xsl:with-param>
        </xsl:call-template>
      </xsl:if>
      <xsl:apply-templates select="*[not(self::label|self::title)]"/>
    </div>
  </xsl:template>
  

  <xsl:template match="textual-form">
    <p class="textual-form">
      <span class="generated">[Textual form] </span>
      <xsl:apply-templates/>
    </p>
  </xsl:template>
  


  <xsl:template match="glossary/glossary | gloss-group/gloss-group">
    <!-- the same document shouldn't have both types -->
    <div class="glossary">
      <xsl:call-template name="named-anchor"/>
      <xsl:apply-templates/>
    </div>
  </xsl:template>
  


  <xsl:template match="graphic | inline-graphic">
    <xsl:apply-templates/>
    <!-- No alt-text: fall back to an empty alt rather than the file
         name, which screen readers would read aloud ("douglas treaties
         colour map 3 dot jpg"). Enter real alt text in the editor. -->
    <img alt="">
      <xsl:for-each select="alt-text">
        <xsl:attribute name="alt">
          <xsl:value-of select="normalize-space(string(.))"/>
        </xsl:attribute>
      </xsl:for-each>
      <xsl:call-template name="assign-src"/>
    </img>
  </xsl:template>
  
  
  <xsl:template match="alt-text">
    <!-- handled with graphic or inline-graphic -->
  </xsl:template>
  

  <xsl:template match="list">
    <div class="list">
      <xsl:call-template name="named-anchor"/>
      <xsl:apply-templates select="label | title"/>
      <xsl:apply-templates select="." mode="list"/>
    </div>
  </xsl:template>
  

  <xsl:template priority="2" mode="list"
    match="list[@list-type='simple' or list-item/label]">
    <ul style="list-style-type: none">
      <xsl:apply-templates select="list-item"/>
    </ul>
  </xsl:template>


  <xsl:template match="list[@list-type='bullet' or not(@list-type)]" mode="list">
    <ul>
      <xsl:apply-templates select="list-item"/>
    </ul>
  </xsl:template>


  <xsl:template match="list" mode="list">
    <xsl:variable name="style">
      <xsl:choose>
        <xsl:when test="@list-type='alpha-lower'">lower-alpha</xsl:when>
        <xsl:when test="@list-type='alpha-upper'">upper-alpha</xsl:when>
        <xsl:when test="@list-type='roman-lower'">lower-roman</xsl:when>
        <xsl:when test="@list-type='roman-upper'">upper-roman</xsl:when>
        <xsl:otherwise>decimal</xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    <ol style="list-style-type: {$style}">
      <xsl:apply-templates select="list-item"/>
    </ol>
  </xsl:template>
  

	<xsl:template match="list-item">
		<li>
			<xsl:apply-templates/>
		</li>
	</xsl:template>


	<xsl:template match="list-item/label">
	  <!-- if the next sibling is a p, the label will be called as
	       a run-in -->
	  <xsl:if test="following-sibling::*[1][not(self::p)]">
	    <xsl:call-template name="label"/>
	  </xsl:if>
	</xsl:template>
  
  
	<!-- An audio clip (BC Studies' "Audio clip" block): a player the reader
	     can use in the page, with a plain download link under it. The src is
	     the bare filename from the XML; OJS rewrites it to the dependent file
	     of the HTML galley with that Name, and an unzipped galley plays it
	     straight off disk because the file sits beside the .html. -->
	<!-- The players are printed at the TOP of the galley, under the journal
	     line and above the abstract (see the front-matter template), because
	     in a piece like a podcast the audio is the thing the reader came for.
	     So a clip renders nothing where it sits in the body. -->
	<xsl:template match="media[@mimetype='audio']"/>


	<!-- All of an article's clips share ONE box, laid out like the audio
	     playlist on bcstudies.ubc.ca: the current episode's title and
	     caption, a single player, then a numbered track list. Clicking a
	     track loads it into the player, and each episode runs on to the
	     next. Without the script the track titles are plain links to the
	     files, so every episode is still reachable. A lone clip gets the
	     same box without the track list. -->
	<xsl:template name="audio-playlist">
		<xsl:param name="clips"/>
		<xsl:if test="$clips">
			<xsl:variable name="several" select="count($clips) &gt; 1"/>
			<div class="media audio panel audio-playlist">
				<xsl:if test="not($several)">
					<xsl:for-each select="$clips">
						<xsl:call-template name="named-anchor"/>
					</xsl:for-each>
				</xsl:if>
				<div class="audio-playlist-current" aria-live="polite">
					<xsl:for-each select="$clips[1]">
						<xsl:call-template name="audio-track-text"/>
					</xsl:for-each>
				</div>
				<audio controls="controls" preload="metadata" src="{$clips[1]/@xlink:href}">
					<a href="{$clips[1]/@xlink:href}">Download the audio</a>
				</audio>
				<xsl:choose>
					<xsl:when test="$several">
						<ol class="audio-playlist-tracks">
							<xsl:for-each select="$clips">
								<li class="audio-playlist-item">
									<xsl:if test="position() = 1">
										<xsl:attribute name="class">audio-playlist-item is-current</xsl:attribute>
									</xsl:if>
									<xsl:call-template name="named-anchor"/>
									<a class="audio-playlist-track" href="{@xlink:href}">
										<xsl:if test="position() = 1">
											<xsl:attribute name="aria-current">true</xsl:attribute>
										</xsl:if>
										<span class="audio-playlist-number">
											<xsl:value-of select="position()"/>
											<xsl:text>.</xsl:text>
										</span>
										<xsl:text> </xsl:text>
										<span class="audio-playlist-title">
											<xsl:call-template name="audio-track-name"/>
										</span>
										<span class="audio-playlist-length"></span>
									</a>
									<a class="audio-playlist-download" href="{@xlink:href}" download="">
										<xsl:text>Download</xsl:text>
										<span class="visually-hidden">
											<xsl:text> </xsl:text>
											<xsl:call-template name="audio-track-name"/>
										</span>
									</a>
									<!-- the caption the header shows while this track is loaded;
									     the first track's is already in the header, and writing
									     it twice would repeat its paragraph ids -->
									<xsl:if test="position() &gt; 1">
										<div class="audio-playlist-text" hidden="hidden">
											<xsl:call-template name="audio-track-text"/>
										</div>
									</xsl:if>
								</li>
							</xsl:for-each>
						</ol>
					</xsl:when>
					<xsl:otherwise>
						<p class="media-download">
							<a href="{$clips[1]/@xlink:href}" download="">Download audio</a>
						</p>
					</xsl:otherwise>
				</xsl:choose>
			</div>
			<xsl:if test="$several">
				<xsl:call-template name="audio-playlist-script"/>
			</xsl:if>
		</xsl:if>
	</xsl:template>


	<!-- A clip's name in the track list: its label, else its caption
	     title, else the filename. -->
	<xsl:template name="audio-track-name">
		<xsl:choose>
			<xsl:when test="normalize-space(label)">
				<xsl:apply-templates select="label/node()"/>
			</xsl:when>
			<xsl:when test="normalize-space(caption/title)">
				<xsl:apply-templates select="caption/title/node()"/>
			</xsl:when>
			<xsl:otherwise>
				<xsl:value-of select="@xlink:href"/>
			</xsl:otherwise>
		</xsl:choose>
	</xsl:template>


	<!-- A clip's label and caption, for the top of the playlist box. -->
	<xsl:template name="audio-track-text">
		<xsl:apply-templates select="." mode="label"/>
		<xsl:apply-templates select="caption"/>
	</xsl:template>


	<xsl:template name="audio-playlist-script">
		<script type="text/javascript"><![CDATA[
(function () {
  "use strict";
  var box = document.querySelector(".audio-playlist");
  if (!box) { return; }
  var player = box.querySelector("audio");
  var current = box.querySelector(".audio-playlist-current");
  var items = Array.prototype.slice.call(box.querySelectorAll(".audio-playlist-item"));
  if (!player || !items.length) { return; }
  var at = 0;

  /* what the header shows for each track: the first track's is the header
     as printed, the others come from their hidden copies */
  var texts = items.map(function (item, i) {
    var t = i === 0 ? current : item.querySelector(".audio-playlist-text");
    var copy = t ? t.cloneNode(true) : document.createElement("div");
    Array.prototype.forEach.call(copy.querySelectorAll("[id]"), function (el) {
      el.removeAttribute("id");
    });
    return copy;
  });

  function fmt(sec) {
    if (!isFinite(sec) || sec <= 0) { return ""; }
    sec = Math.round(sec);
    var h = Math.floor(sec / 3600), m = Math.floor(sec % 3600 / 60), s = sec % 60;
    var ss = (s < 10 ? "0" : "") + s;
    return h ? h + ":" + (m < 10 ? "0" : "") + m + ":" + ss : m + ":" + ss;
  }

  function load(i, play) {
    var item = items[i];
    var link = item.querySelector(".audio-playlist-track");
    items[at].classList.remove("is-current");
    items[at].querySelector(".audio-playlist-track").removeAttribute("aria-current");
    at = i;
    item.classList.add("is-current");
    link.setAttribute("aria-current", "true");
    if (current) { current.innerHTML = texts[i].innerHTML; }
    player.src = link.getAttribute("href");
    if (play) {
      var p = player.play();
      if (p && p.catch) { p.catch(function () {}); }
    }
  }

  items.forEach(function (item, i) {
    var link = item.querySelector(".audio-playlist-track");
    link.addEventListener("click", function (e) {
      e.preventDefault();
      if (i === at) {
        if (player.paused) { player.play(); } else { player.pause(); }
      } else {
        load(i, true);
      }
    });
    /* each episode's running time, read from the file's header only */
    var probe = document.createElement("audio");
    probe.preload = "metadata";
    probe.addEventListener("loadedmetadata", function () {
      var len = item.querySelector(".audio-playlist-length");
      if (len) { len.textContent = fmt(probe.duration); }
      probe.removeAttribute("src");
    });
    probe.src = link.getAttribute("href");
  });

  player.addEventListener("ended", function () {
    if (at + 1 < items.length) { load(at + 1, true); }
  });
}());
]]></script>
	</xsl:template>


	<xsl:template match="media">
		<a>
			<xsl:call-template name="assign-id"/>
			<xsl:call-template name="assign-href"/>
			<xsl:apply-templates/>
		</a>
	</xsl:template>


  <xsl:template match="p | license-p">
    <p>
      <xsl:if test="not(preceding-sibling::*)">
        <xsl:attribute name="class">first</xsl:attribute>
      </xsl:if>
      <xsl:call-template name="assign-id"/>
      <xsl:apply-templates select="@content-type"/>
      <xsl:apply-templates/>
    </p>
  </xsl:template>
  
  
  <xsl:template match="@content-type">
    <!-- <span class="generated">[</span>
    <xsl:value-of select="."/>
    <span class="generated">] </span> -->
  </xsl:template>


  <xsl:template match="list-item/p[not(preceding-sibling::*[not(self::label)])]">
    <p>
      <xsl:call-template name="assign-id"/>
      <xsl:for-each select="preceding-sibling::label">
        <span class="label">
          <xsl:apply-templates/>
        </span>
      <xsl:text> </xsl:text>
      </xsl:for-each>
      <xsl:apply-templates select="@content-type"/>
      <xsl:apply-templates/>
    </p>
  </xsl:template>


  <xsl:template match="product">
    <p class="product">
      <xsl:call-template name="assign-id"/>
      <xsl:apply-templates/>
    </p>
  </xsl:template>


  <xsl:template match="permissions">
    <div class="permissions">
    <xsl:apply-templates select="copyright-statement"/>
    <xsl:if test="copyright-year | copyright-holder">
      <p class="copyright">
        <span class="generated-hidden">Copyright</span>
        <xsl:for-each select="copyright-year | copyright-holder">
            <xsl:apply-templates/>
            <xsl:if test="not(position()=last())">
              <span class="generated-hidden">, </span>
            </xsl:if>
        </xsl:for-each>
      </p>
    </xsl:if>
    <xsl:apply-templates select="license"/>
    </div>
  </xsl:template>
  
  
  <xsl:template match="copyright-statement">
    <p class="copyright">
      <xsl:apply-templates></xsl:apply-templates>
    </p>
  </xsl:template>


  <xsl:template match="def-list">
    <div class="def-list">
      <xsl:call-template name="named-anchor"/>
      <xsl:apply-templates select="label | title"/>
      <div class="def-list table">
        <xsl:if test="term-head|def-head">
          <div class="row">
            <div class="cell def-list-head">
              <xsl:apply-templates select="term-head"/>
            </div>
            <div class="cell def-list-head">
              <xsl:apply-templates select="def-head"/>
            </div>
          </div>
        </xsl:if>
        <xsl:apply-templates select="def-item"/>
      </div>
      <xsl:apply-templates select="def-list"/>
    </div>
  </xsl:template>


	<xsl:template match="def-item">
		<div class="def-item row">
			<xsl:call-template name="assign-id"/>
			<xsl:apply-templates/>
		</div>
	</xsl:template>


	<xsl:template match="term">
		<div class="def-term cell">
			<xsl:call-template name="assign-id"/>
		  <p>
				<xsl:apply-templates/>
		  </p>
		</div>
	</xsl:template>


	<xsl:template match="def">
		<div class="def-def cell">
			<xsl:call-template name="assign-id"/>
			<xsl:apply-templates/>
		</div>
	</xsl:template>


  <xsl:template match="disp-quote">
    <div class="blockquote">
      <xsl:call-template name="named-anchor"/>
      <xsl:apply-templates/>
    </div>
  </xsl:template>


  <xsl:template match="preformat">
    <pre class="preformat">
      <xsl:apply-templates/>
    </pre>
  </xsl:template>


  <xsl:template match="alternatives | name-alternatives | collab-alternatives | aff-alternatives">
    <xsl:apply-templates/>
  </xsl:template>
  
  
  <xsl:template match="citation-alternatives" priority="2">
    <!-- priority bumped to supersede match on ref/* -->
    <!-- may appear in license-p, p, ref, td, th, title  -->
    <xsl:apply-templates/>
  </xsl:template>
  
  
  <xsl:template match="ref">
      <div class="row">
        <div class="ref-label cell">
          <p class="ref-label">
            <xsl:apply-templates select="." mode="label"/>
            <xsl:text>&#xA0;</xsl:text>
            <!-- space forces vertical alignment of the paragraph -->
            <xsl:call-template name="named-anchor"/>
          </p>
        </div>
        <div class="ref-content cell">
          <xsl:apply-templates/>
        </div>
      </div>
  </xsl:template>
    
    <!-- ================================================================= -->
  <!-- WORKS CITED BIDIRECTIONAL LINKING                                 -->
  <!-- ================================================================= -->

  <!-- 1. Inline Works Cited Link (<xref ref-type="bibr">) in Main Text -->
    <xsl:template match="xref[@ref-type='bibr']" priority="2">
      <!-- Capture the target reference ID assigned in the XML -->
      <xsl:variable name="rid" select="@rid"/>
      <!-- Generate a unique return ID based on this specific citation node -->
      <xsl:variable name="citeId" select="generate-id(.)"/>
      
      <span id="{$citeId}">
        <a href="#{$rid}" class="xref">
          <xsl:apply-templates/>
        </a>
      </span>
    </xsl:template>
  
    <!-- 2. The Reference Item (<ref>) in the Bibliography Section -->
    <xsl:template match="ref" priority="2">
      <!-- Grab its existing XML ID attribute -->
      <xsl:variable name="id" select="@id"/>
      
      <!-- Find the VERY FIRST inline xref in the text that points to this specific reference -->
      <xsl:variable name="firstXref" select="(//xref[@ref-type='bibr' and @rid=$id])[1]"/>
      
      <li id="{$id}" class="ref-entry">
        <xsl:call-template name="ref-export-data"/>
        <!-- Output the reference contents (authors, title, year, source, etc.) -->
        <xsl:apply-templates/>
        
        <!-- Only insert a return jump anchor if an active inline citation exists -->
        <xsl:if test="$firstXref">
          <a href="#{generate-id($firstXref)}" aria-label="Jump back to context" class="xref" style="margin-left: 5px;">&#8617;</a>
        </xsl:if>
      </li>
    </xsl:template>
  <!-- The parts of a reference as data-* attributes on its <li>, for the
       "Export references" bar the galley script builds (RIS, BibTeX, plain
       text). Read from the element-citation, the structured copy that is
       otherwise not shown; a reference with only a mixed-citation falls
       back to that. Several people go in one attribute separated by "|".
       Context: ref. -->
  <xsl:template name="ref-export-data">
    <xsl:variable name="c"
      select="(.//element-citation | .//mixed-citation[not(ancestor::ref[1]//element-citation)])[1]"/>
    <xsl:if test="$c">
      <xsl:attribute name="data-type">
        <xsl:value-of select="$c/@publication-type"/>
      </xsl:attribute>
      <xsl:variable name="authors"
        select="$c/person-group[not(@person-group-type) or @person-group-type = 'author']/*[self::name or self::string-name or self::collab]
                | $c/name | $c/string-name | $c/collab"/>
      <xsl:if test="$authors">
        <xsl:attribute name="data-authors">
          <xsl:for-each select="$authors">
            <xsl:if test="position() &gt; 1">|</xsl:if>
            <xsl:call-template name="ref-export-name"/>
          </xsl:for-each>
        </xsl:attribute>
      </xsl:if>
      <xsl:variable name="editors"
        select="$c/person-group[@person-group-type = 'editor']/*[self::name or self::string-name or self::collab]"/>
      <xsl:if test="$editors">
        <xsl:attribute name="data-editors">
          <xsl:for-each select="$editors">
            <xsl:if test="position() &gt; 1">|</xsl:if>
            <xsl:call-template name="ref-export-name"/>
          </xsl:for-each>
        </xsl:attribute>
      </xsl:if>
      <xsl:call-template name="ref-export-attr">
        <xsl:with-param name="name" select="'title'"/>
        <xsl:with-param name="node" select="($c/article-title | $c/chapter-title)[1]"/>
      </xsl:call-template>
      <xsl:call-template name="ref-export-attr">
        <xsl:with-param name="name" select="'source'"/>
        <xsl:with-param name="node" select="$c/source[1]"/>
      </xsl:call-template>
      <xsl:call-template name="ref-export-attr">
        <xsl:with-param name="name" select="'series'"/>
        <xsl:with-param name="node" select="$c/series[1]"/>
      </xsl:call-template>
      <xsl:call-template name="ref-export-attr">
        <xsl:with-param name="name" select="'year'"/>
        <xsl:with-param name="node" select="$c/year[1]"/>
      </xsl:call-template>
      <xsl:call-template name="ref-export-attr">
        <xsl:with-param name="name" select="'volume'"/>
        <xsl:with-param name="node" select="$c/volume[1]"/>
      </xsl:call-template>
      <xsl:call-template name="ref-export-attr">
        <xsl:with-param name="name" select="'issue'"/>
        <xsl:with-param name="node" select="$c/issue[1]"/>
      </xsl:call-template>
      <xsl:call-template name="ref-export-attr">
        <xsl:with-param name="name" select="'fpage'"/>
        <xsl:with-param name="node" select="($c/fpage | $c/elocation-id)[1]"/>
      </xsl:call-template>
      <xsl:call-template name="ref-export-attr">
        <xsl:with-param name="name" select="'lpage'"/>
        <xsl:with-param name="node" select="$c/lpage[1]"/>
      </xsl:call-template>
      <xsl:call-template name="ref-export-attr">
        <xsl:with-param name="name" select="'publisher'"/>
        <xsl:with-param name="node" select="$c/publisher-name[1]"/>
      </xsl:call-template>
      <xsl:call-template name="ref-export-attr">
        <xsl:with-param name="name" select="'place'"/>
        <xsl:with-param name="node" select="$c/publisher-loc[1]"/>
      </xsl:call-template>
      <xsl:call-template name="ref-export-attr">
        <xsl:with-param name="name" select="'isbn'"/>
        <xsl:with-param name="node" select="$c/isbn[1]"/>
      </xsl:call-template>
      <xsl:call-template name="ref-export-attr">
        <xsl:with-param name="name" select="'doi'"/>
        <xsl:with-param name="node" select="$c/pub-id[@pub-id-type = 'doi'][1]"/>
      </xsl:call-template>
      <xsl:variable name="url"
        select="($c/ext-link/@xlink:href | $c/uri/@xlink:href | $c/uri[not(@xlink:href)])[1]"/>
      <xsl:if test="normalize-space($url)">
        <xsl:attribute name="data-url">
          <xsl:value-of select="normalize-space($url)"/>
        </xsl:attribute>
      </xsl:if>
    </xsl:if>
  </xsl:template>

  <!-- one data-* attribute, only when the element is there and not empty -->
  <xsl:template name="ref-export-attr">
    <xsl:param name="name"/>
    <xsl:param name="node"/>
    <xsl:if test="normalize-space(string($node))">
      <xsl:attribute name="data-{$name}">
        <xsl:value-of select="normalize-space(string($node))"/>
      </xsl:attribute>
    </xsl:if>
  </xsl:template>

  <!-- "Surname, Given" (or the collab's name). Context: name, string-name
       or collab. -->
  <xsl:template name="ref-export-name">
    <xsl:choose>
      <xsl:when test="surname">
        <xsl:value-of select="normalize-space(string(surname))"/>
        <xsl:if test="normalize-space(string(given-names))">
          <xsl:text>, </xsl:text>
          <xsl:value-of select="normalize-space(string(given-names))"/>
        </xsl:if>
      </xsl:when>
      <xsl:otherwise>
        <xsl:value-of select="normalize-space(string(.))"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

    <!-- ================================================================= -->
  <!-- FOOTNOTE BIDIRECTIONAL LINKING                                    -->
  <!-- ================================================================= -->

  <!-- 1. In-text callout: <xref ref-type="fn" rid="fn3">3</xref> -->
  <xsl:template match="xref[@ref-type='fn']" priority="2">
    <xsl:variable name="rid" select="@rid"/>
    <span id="{generate-id(.)}" class="fn-callout">
      <a href="#{$rid}" class="xref">
        <xsl:choose>
          <xsl:when test="normalize-space(string(.))">
            <xsl:apply-templates/>
          </xsl:when>
          <xsl:otherwise>
            <!-- empty callout: borrow the note's own label -->
            <xsl:apply-templates select="key('element-by-id',$rid)" mode="label-text">
              <xsl:with-param name="warning" select="true()"/>
            </xsl:apply-templates>
          </xsl:otherwise>
        </xsl:choose>
      </a>
    </span>
  </xsl:template>

  <!-- 2. The return arrow itself, shared by both profiles -->
  <xsl:template name="fn-return-link">
    <xsl:variable name="firstCallout"
      select="(key('xref-by-rid',@id)[@ref-type='fn'])[1]"/>
    <xsl:if test="@id and $firstCallout">
      <a href="#{generate-id($firstCallout)}" class="xref fn-return"
         aria-label="Jump back to text" style="margin-left: 5px;">&#8617;</a>
    </xsl:if>
  </xsl:template>

  <!-- 3. lens profile: the numbered note paragraph in the body Notes sec -->
  <xsl:template match="p[@content-type='endnote']" priority="2">
    <p class="endnote">
      <xsl:call-template name="assign-id"/>
      <xsl:apply-templates/>
      <xsl:call-template name="fn-return-link"/>
    </p>
  </xsl:template>

  <xsl:template match="ref/* | ref/citation-alternatives/*" priority="0">
    <!-- should match mixed-citation, element-citation, nlm-citation,
         or citation (in 2.3); note and label should be matched below;
         citation-alternatives is handled elsewhere -->
    <p class="citation">
      <xsl:call-template name="named-anchor"/>
      <xsl:apply-templates/>
    </p>
  </xsl:template>
  
  <!-- priority="1" is required: the generic "ref/* | ref/citation-alternatives/*"
       template below is declared with priority="0", which is also the default
       priority of a bare element-name pattern. Two matching templates of equal
       priority is an error in XSLT 1.0 -->
  <xsl:template match="mixed-citation" priority="1">
    <div class="mixed-citation">
      <xsl:apply-templates/>
    </div>
  </xsl:template>

  <!-- Every <ref> carries BOTH a mixed-citation (the text as printed) and an
       element-citation (structured, for aggregators). Rendering both
       showed each reference twice; it was only hidden by a CSS rule, so any
       failure to load style.css exposed unpunctuated citation soup. Suppress
       the structured copy at source whenever the readable one is present. -->
  <xsl:template match="element-citation[../mixed-citation]" priority="3"/>

  <xsl:template match="element-citation" priority="1">
    <div class="element-citation">
      <xsl:apply-templates/>
    </div>
  </xsl:template>

  <xsl:template match="ref/note" priority="2">
    <xsl:param name="label" select="''"/>
    <xsl:if test="normalize-space(string($label))
      and not(preceding-sibling::*[not(self::label)])">
      <p class="label">
          <xsl:copy-of select="$label"/>
      </p>
    </xsl:if>
    <div class="note">
      <xsl:call-template name="named-anchor"/>
      <xsl:apply-templates/>
    </div>
  </xsl:template>
  
  
  <xsl:template match="app/related-article |
    app-group/related-article | bio/related-article | 
    body/related-article | boxed-text/related-article | 
    disp-quote/related-article | glossary/related-article |
    gloss-group/related-article |
    ref-list/related-article | sec/related-article">
    <xsl:apply-templates select="." mode="metadata"/>
  </xsl:template>
  
  
  <xsl:template match="app/related-object |
    app-group/related-object | bio/related-object |
    body/related-object | boxed-text/related-object | 
    disp-quote/related-object | glossary/related-object |
    gloss-group/related-article |
    ref-list/related-object | sec/related-object">
    <xsl:apply-templates select="." mode="metadata"/>
  </xsl:template>
  
  
  <xsl:template match="speech">
    <div class="speech">
      <xsl:call-template name="named-anchor"/>
      <xsl:apply-templates mode="speech"/>
    </div>
  </xsl:template>
  
  
  <xsl:template match="speech/speaker" mode="speech"/>
    
    
  <xsl:template match="speech/p" mode="speech">
    <p>
      <xsl:apply-templates select="self::p[not(preceding-sibling::p)]/../speaker"/>
      <xsl:apply-templates/>
    </p>
  </xsl:template>
  
  
  <xsl:template match="speech/speaker">
    <b>
      <xsl:apply-templates/>
    </b>
    <span class="generated">: </span>
  </xsl:template>
  
  
  <xsl:template match="supplementary-material">
    <div class="panel">
      <xsl:call-template name="named-anchor"/>
      <xsl:apply-templates select="." mode="label"/>
      <xsl:apply-templates/>
    </div>
  </xsl:template>
  

	<xsl:template match="tex-math">
		<span class="tex-math">
			<span class="generated">[TeX:] </span>
			<xsl:apply-templates/>
		</span>
	</xsl:template>

  
  <xsl:template match="mml:*">
    <!-- this stylesheet simply copies MathML through. If your browser
         supports it, you will get it -->
    <xsl:copy>
      <xsl:copy-of select="@*"/>
      <xsl:apply-templates/>
    </xsl:copy>
  </xsl:template>
  
  
  <xsl:template match="verse-group">
    <div class="verse">
      <xsl:call-template name="named-anchor"/>
      <xsl:apply-templates/>
    </div>
  </xsl:template>
  

  <xsl:template match="verse-line">
    <p class="verse-line">
      <xsl:apply-templates/>
    </p>
    <xsl:if test="position() = last()">
        <br />
    </xsl:if>
  </xsl:template>
  

  <xsl:template match="aff/label | corresp/label | chem-struct/label |
    mixed-citation/label | citation/label">
    <!-- these labels appear in line -->
    <span class="generated">[</span>
    <xsl:apply-templates/>
    <span class="generated">] </span>
  </xsl:template>


  <xsl:template match="app/label | boxed-text/label |
    chem-struct-wrap/label | chem-struct-wrapper/label |
    disp-formula/label | fig/label | fn/label | ref/label |
    statement/label | supplementary-material/label | table-wrap/label"
    priority="2">
    <!-- suppressed, since acquired by their parents in mode="label" -->
  </xsl:template>


  <xsl:template match="p/label">
    <span class="label">
      <xsl:apply-templates/>
    </span>
  </xsl:template>
  
  <xsl:template match="label" name="label">
    <!-- other labels are displayed as blocks. Not a heading: an <h5>
         straight after an <h2> section heading skips levels, and screen
         reader users navigating by heading would land on "Figure 1". -->
    <div class="label">
      <xsl:apply-templates/>
    </div>
  </xsl:template>
  
  
  <!-- ============================================================= -->
  <!--  TABLES                                                       -->
  <!-- ============================================================= -->
  <!--  Tables are already in XHTML, and can simply be copied
        through                                                      -->
  
  
  <!-- No named anchor here: an <a> is not allowed directly inside a
       table, thead or tr, and browsers move it out above the table. Any
       @id the element really has is copied as an attribute instead. -->
  <xsl:template match="table | thead | tbody | tfoot |
      col | colgroup | tr | th | td">
    <xsl:copy>
      <xsl:apply-templates select="@*" mode="table-copy"/>
      <xsl:apply-templates/>
    </xsl:copy>
  </xsl:template>
  
  
  <xsl:template match="array/tbody">
    <table>
      <xsl:copy>
      <xsl:apply-templates select="@*" mode="table-copy"/>
      <xsl:call-template name="named-anchor"/>
      <xsl:apply-templates/>
    </xsl:copy>
    </table>
  </xsl:template>
  
  
  <xsl:template match="@*" mode="table-copy">
    <xsl:copy-of select="."/>
  </xsl:template>
  
  
  <xsl:template match="@content-type" mode="table-copy"/>
  
  
  <!-- ============================================================= -->
  <!--  INLINE MISCELLANEOUS                                         -->
  <!-- ============================================================= -->
  <!--  Templates strictly for formatting follow; these are templates
        to handle various inline structures -->


  <xsl:template match="abbrev">
    <xsl:apply-templates/>
  </xsl:template>
  
  <xsl:template match="abbrev[normalize-space(string(@xlink:href))]">
    <a>
      <xsl:call-template name="assign-href"/>
      <xsl:apply-templates/>
    </a>
  </xsl:template>
    
  <xsl:template match="abbrev/def">
    <xsl:text>[</xsl:text>
    <xsl:apply-templates/>
    <xsl:text>]</xsl:text>
  </xsl:template>
  
  <xsl:template match="p/address | license-p/address |
    named-content/p | styled-content/p">
    <xsl:apply-templates mode="inline"/>
  </xsl:template>
  
  
  <xsl:template match="address/*" mode="inline">
    <xsl:if test="preceding-sibling::*">
      <span class="generated">, </span>
    </xsl:if>
    <xsl:apply-templates/>
  </xsl:template>
  
        
  <xsl:template match="award-id">
    <xsl:apply-templates/>
  </xsl:template>
  
    
  <xsl:template match="award-id[normalize-space(string(@rid))]">
    <a href="#{@rid}">
      <xsl:apply-templates/>
    </a>
  </xsl:template>
  
    
  <xsl:template match="break">
    <br class="br"/>
  </xsl:template>


  <xsl:template match="email">
    <a href="mailto:{.}">
      <xsl:apply-templates/>
    </a>
  </xsl:template>

  
  <xsl:template match="ext-link | uri | inline-supplementary-material">
    <a target="xrefwindow" rel="noopener noreferrer">
      <xsl:attribute name="href">
        <xsl:value-of select="."/>
      </xsl:attribute>
      <!-- if an @href is present, it overrides the href
           just attached -->
      <xsl:call-template name="assign-href"/>
      <xsl:call-template name="assign-id"/>
      <xsl:apply-templates/>
      <xsl:if test="not(normalize-space(string(.)))">
        <xsl:value-of select="@xlink:href"/>
      </xsl:if>
    </a>
  </xsl:template>


  <xsl:template match="funding-source">
    <span class="funding-source">
      <xsl:apply-templates/>
    </span>
  </xsl:template>
  

  <xsl:template match="hr">
    <hr class="hr"/>
  </xsl:template>
  

  <!-- inline-graphic is handled above, with graphic -->
  
  
  <xsl:template match="inline-formula | chem-struct">
    <span class="{local-name()}">
      <xsl:apply-templates/>
    </span>
  </xsl:template>


  <xsl:template match="chem-struct-wrap/chem-struct | chem-struct-wrapper/chem-struct">
    <div class="{local-name()}">
      <xsl:apply-templates/>
    </div>
  </xsl:template>

  
  <xsl:template match="milestone-start | milestone-end">
    <span class="{substring-after(local-name(),'milestone-')}">
      <xsl:comment>
        <xsl:value-of select="@rationale"/>
      </xsl:comment>
    </span>
  </xsl:template>
  

  <xsl:template match="object-id">
    <span class="{local-name()}">
      <xsl:apply-templates/>
    </span>
  </xsl:template>
  

  <!-- preformat is handled above -->
  
  <xsl:template match="sig">
    <xsl:apply-templates/>
  </xsl:template>
  

  <xsl:template match="target">
    <xsl:call-template name="named-anchor"/>
  </xsl:template>
  
  
  <xsl:template match="styled-content">
    <span>
      <xsl:copy-of select="@style"/>
      <xsl:for-each select="@style-type">
        <xsl:attribute name="class">
          <xsl:value-of select="."/>
        </xsl:attribute>
      </xsl:for-each>
      <!-- carry xml:lang through as HTML lang so the browser picks a font
           that has the characters (Cherokee, Inuktitut syllabics, etc.) -->
      <xsl:for-each select="@xml:lang">
        <xsl:attribute name="lang">
          <xsl:value-of select="."/>
        </xsl:attribute>
      </xsl:for-each>
      <!-- An Indigenous-language word is not English text that happens to
           look odd. translate="no" stops in-browser translation (Chrome,
           Edge, Safari) from rewriting it, and spellcheck="false" stops an
           editable view from redlining it. Both are what keeps the word on
           the page as the author wrote it. -->
      <xsl:if test="@style-type = 'special-characters'">
        <xsl:attribute name="translate">no</xsl:attribute>
        <xsl:attribute name="spellcheck">false</xsl:attribute>
      </xsl:if>
      <xsl:apply-templates/>
    </span>
  </xsl:template>
  
  
  <xsl:template match="named-content">
    <span>
      <xsl:for-each select="@content-type">
        <xsl:attribute name="class">
          <xsl:value-of select="translate(.,' ','-')"/>
        </xsl:attribute>
      </xsl:for-each>
      <xsl:apply-templates/>
    </span>
  </xsl:template>
  
  
  <xsl:template match="private-char">
    <span>
      <xsl:for-each select="@description">
        <xsl:attribute name="title">
          <xsl:value-of select="."/>
        </xsl:attribute>
      </xsl:for-each>
      <span class="generated">[Private character </span>
      <xsl:for-each select="@name">
        <xsl:text> </xsl:text>
        <xsl:value-of select="."/>
      </xsl:for-each>
      <span class="generated">]</span>
    </span>
  </xsl:template>
  
  
  <xsl:template match="glyph-data | glyph-ref">
    <span class="generated">(Glyph not rendered)</span>
  </xsl:template>
    
  
  <xsl:template match="related-article">
    <span class="generated">[Related article:] </span>
    <xsl:apply-templates/>
  </xsl:template>
  
  
  <xsl:template match="related-object">
    <span class="generated">[Related object:] </span>
    <xsl:apply-templates/>
  </xsl:template>
  
  
  <xsl:template match="xref[not(normalize-space(string(.)))]">
    <a href="#{@rid}">
      <xsl:apply-templates select="key('element-by-id',@rid)"
        mode="label-text">
        <xsl:with-param name="warning" select="true()"/>
      </xsl:apply-templates>
    </a>
  </xsl:template>


  <xsl:template match="xref">
    <a href="#{@rid}">
      <xsl:apply-templates/>
    </a>
  </xsl:template>


  
  <!-- ============================================================= -->
  <!--  Formatting elements                                          -->
  <!-- ============================================================= -->


  <xsl:template match="bold">
    <b>
      <xsl:apply-templates/>
    </b>
  </xsl:template>


  <xsl:template match="italic">
    <i>
      <xsl:apply-templates/>
    </i>
  </xsl:template>


  <xsl:template match="monospace">
    <tt>
      <xsl:apply-templates/>
    </tt>
  </xsl:template>


  <xsl:template match="overline">
    <span style="text-decoration: overline">
      <xsl:apply-templates/>
    </span>
  </xsl:template>


  <xsl:template match="price">
    <span class="price">
      <xsl:apply-templates/>
    </span>
  </xsl:template>


  <xsl:template match="roman">
    <span style="font-style: normal">
      <xsl:apply-templates/>
    </span>
  </xsl:template>


  <xsl:template match="sans-serif">
    <span style="font-family: sans-serif; font-size: 80%">
      <xsl:apply-templates/>
    </span>
  </xsl:template>


  <xsl:template match="sc">
    <span class="sc">
      <xsl:apply-templates/>
    </span>
  </xsl:template>


  <xsl:template match="strike">
    <span style="text-decoration: line-through">
      <xsl:apply-templates/>
    </span>
  </xsl:template>


  <xsl:template match="sub">
    <sub>
      <xsl:apply-templates/>
    </sub>
  </xsl:template>


  <xsl:template match="sup">
    <sup>
      <xsl:apply-templates/>
    </sup>
  </xsl:template>


  <xsl:template match="underline">
    <span style="text-decoration: underline">
      <xsl:apply-templates/>
    </span>
  </xsl:template>


  <!-- ============================================================= -->
  <!--  BACK MATTER                                                  -->
  <!-- ============================================================= -->


  <xsl:variable name="loose-footnotes"
    select="//fn[not(ancestor::front|parent::fn-group|ancestor::table-wrap)]"/>
    
    
  <xsl:template name="make-back">
    <xsl:apply-templates select="back"/>
    <xsl:if test="not(back)">
      <xsl:call-template name="funding-section"/>
    </xsl:if>
    <xsl:if test="$loose-footnotes and not(back)">
      <!-- autogenerating a section for footnotes only if there is no
           back element, and if footnotes exist for it -->
      <xsl:call-template name="footnotes"/>
    </xsl:if>
  </xsl:template>
    
  <xsl:template match="back">
    <!-- content model for back: 
          (label?, title*, 
          (ack | app-group | bio | fn-group | glossary | ref-list |
           notes | sec)*) -->
    <xsl:if test="not(fn-group) and $loose-footnotes">
      <xsl:call-template name="footnotes"/>
    </xsl:if>
    <!-- BC Studies: the funding statement lives in article-meta (where
         Crossref reads it), but readers expect it with the other closing
         statements, straight after the acknowledgements -->
    <xsl:apply-templates select="ack"/>
    <xsl:call-template name="funding-section"/>
    <xsl:apply-templates select="node()[not(self::ack)]"/>
  </xsl:template>


  <!-- Called with the article (no back) or its back as context. -->
  <xsl:template name="funding-section">
    <xsl:variable name="fg"
      select="(ancestor-or-self::article[1]/front/article-meta
               | ../front-stub | front-stub)/funding-group[funding-statement][1]"/>
    <xsl:for-each select="$fg">
      <div class="back-section">
        <xsl:call-template name="named-anchor"/>
        <xsl:call-template name="main-title">
          <xsl:with-param name="contents">Funding</xsl:with-param>
        </xsl:call-template>
        <xsl:for-each select="funding-statement">
          <p><xsl:apply-templates/></p>
        </xsl:for-each>
      </div>
    </xsl:for-each>
  </xsl:template>
  
  
  <xsl:template name="footnotes">
    <xsl:call-template name="backmatter-section">
      <xsl:with-param name="generated-title">Notes</xsl:with-param>
      <xsl:with-param name="contents">
        <xsl:apply-templates select="$loose-footnotes" mode="footnote"/>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>
  
  
  <xsl:template match="ack">
    <xsl:call-template name="backmatter-section">
      <xsl:with-param name="generated-title">Acknowledgements</xsl:with-param>
    </xsl:call-template>
  </xsl:template>
  

  <xsl:template match="app-group">
    <xsl:call-template name="backmatter-section">
      <xsl:with-param name="generated-title">Appendices</xsl:with-param>
    </xsl:call-template>
  </xsl:template>
  

  <xsl:template match="back/bio">
    <xsl:call-template name="backmatter-section">
      <xsl:with-param name="generated-title">Biography</xsl:with-param>
    </xsl:call-template>
  </xsl:template>
  

  <xsl:template match="back/fn-group">
    <xsl:call-template name="backmatter-section">
      <xsl:with-param name="generated-title">Notes</xsl:with-param>
    </xsl:call-template>
  </xsl:template>
  
  
  <xsl:template match="back/glossary | back/gloss-group">
    <xsl:call-template name="backmatter-section">
      <xsl:with-param name="generated-title">Glossary</xsl:with-param>
    </xsl:call-template>
  </xsl:template>
  

  <!-- The Bibliography of British Columbia: one list per section ("Books
       and Chapters in Books", "Journal Articles", ...), each under its own
       head, with no "References" head over them: the article title
       already says what this is. -->
  <xsl:template match="back/ref-list[@content-type = 'bibliography-of-bc']" priority="2">
    <div class="back-section bibliography-of-bc">
      <xsl:call-template name="named-anchor"/>
      <xsl:for-each select="ref-list[ref]">
        <div class="section ref-list bib-section">
          <xsl:call-template name="named-anchor"/>
          <xsl:call-template name="main-title">
            <xsl:with-param name="contents">
              <xsl:apply-templates select="title/node()"/>
            </xsl:with-param>
          </xsl:call-template>
          <ul class="ref-list-items">
            <xsl:apply-templates select="ref"/>
          </ul>
        </div>
      </xsl:for-each>
    </div>
  </xsl:template>

  <!-- In the Bibliography the authors are set in small caps, as in print.
       Only the names before the title: editors ("edited by ...") stay in
       roman. -->
  <xsl:template priority="2" match="ref-list[@content-type = 'bibliography-of-bc']//mixed-citation/string-name[not(preceding-sibling::article-title | preceding-sibling::chapter-title | preceding-sibling::source)]">
    <span class="sc ref-author"><xsl:apply-templates/></span>
  </xsl:template>

  <xsl:template match="back/ref-list">
    <xsl:call-template name="backmatter-section">
      <xsl:with-param name="generated-title">References</xsl:with-param>
      <xsl:with-param name="contents">
        <xsl:call-template name="ref-list"/>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>
  
  
  <xsl:template match="back/notes">
    <xsl:call-template name="backmatter-section">
      <xsl:with-param name="generated-title">Notes</xsl:with-param>
    </xsl:call-template>
  </xsl:template>
  

  <xsl:template name="backmatter-section">
    <xsl:param name="generated-title"/>
    <xsl:param name="contents">
      <xsl:apply-templates/>
    </xsl:param>
    <div class="back-section">
      <xsl:call-template name="named-anchor"/>
      <xsl:if test="not(title) and $generated-title">
        <xsl:choose>
          <!-- The level of title depends on whether the back matter itself
               has a title -->
          <xsl:when test="ancestor::back/title">
            <xsl:call-template name="section-title">
              <xsl:with-param name="contents" select="$generated-title"/>
            </xsl:call-template>
          </xsl:when>
          <xsl:otherwise>
            <xsl:call-template name="main-title">
              <xsl:with-param name="contents" select="$generated-title"/>
            </xsl:call-template>
          </xsl:otherwise>
        </xsl:choose>
      </xsl:if>
      <xsl:copy-of select="$contents"/>
    </div>
  </xsl:template>
  

  <!-- ============================================================= -->
  <!--  FOOTNOTES                                                    -->
  <!-- ============================================================= -->

  <xsl:template match="fn">
  <!-- Footnotes appearing outside fn-group
       generate cross-references to the footnote,
       which is displayed elsewhere -->
  <!-- Note the rules for displayed content: if any fn elements
       not inside an fn-group (the matched fn or any other) includes
       a label child, all footnotes are expected to have a label
       child. -->
    <xsl:variable name="id">
      <xsl:apply-templates select="." mode="id"/>
    </xsl:variable>
    <a href="#{$id}">
      <xsl:apply-templates select="." mode="label-text">
        <xsl:with-param name="warning" select="true()"/>
      </xsl:apply-templates>
    </a>
  </xsl:template>
  
  <xsl:template match="fn-group/fn | table-wrap-foot/fn |
                       table-wrap-foot/fn-group/fn">
    <xsl:apply-templates select="." mode="footnote"/>
  </xsl:template>
  
  
  <xsl:template match="fn" mode="footnote">
    <div class="footnote">
      <xsl:call-template name="named-anchor"/>
      <xsl:apply-templates/>
    </div>
  </xsl:template>
  
  
  <xsl:template match="fn/p">
    <p>
      <xsl:call-template name="assign-id"/>
      <xsl:if test="not(preceding-sibling::p)">
        <!-- drop an inline label text into the first p -->
        <xsl:apply-templates select="parent::fn" mode="label-text"/>
        <xsl:text> </xsl:text>
      </xsl:if>
      <xsl:apply-templates/>
    </p>
  </xsl:template>
  
  
  <!-- ============================================================= -->
  <!--  MODE 'label-text'
	      Generates label text for elements and their cross-references -->
  <!-- ============================================================= -->
  <!--  This mode is to support auto-numbering and generating of
        labels for certain elements by the stylesheet.
  
        The logic is as follows: for any such element type, if a
        'label' element is ever present, it is expected always to be 
        present; automatic numbering is not performed on any elements
        of that type. For example, the presence of a 'label' element 
        in any 'fig' is taken to indicate that all figs should likewise
        be labeled, and any 'fig' without a label is supposed to be 
        unlabelled (and unnumbered). But if no 'fig' elements have 
        'label' children, labels with numbers are generated for all 
        figs in display.
        
        This logic applies to:
          app, boxed-text, chem-struct-wrap, disp-formula, fig, fn, 
          note, ref, statement, table-wrap.
        
        There is one exception in the case of fn elements, where
        the checking for labels (or for @symbol attributes in the
        case of this element) is performed only within its parent
        fn-group, or in the scope of all fn elements not in an
        fn-group, for fn elements appearing outside fn-group.
        
        In all cases, this logic can be altered simply by overwriting 
        templates in "label" mode for any of these elements.
        
        For other elements, a label is simply displayed if present,
        and auto-numbering is never performed.
        These elements include:
          (label appearing in line) aff, corresp, chem-struct, 
          element-citation, mixed-citation
          
          (label appearing as a block) abstract, ack, app-group, 
          author-notes, back, bio, def-list, disp-formula-group, 
          disp-quote, fn-group, glossary, graphic, kwd-group, 
          list, list-item, media, notes, ref-list, sec, 
          supplementary-material, table-wrap-group, 
          trans-abstract, verse-group -->


  <xsl:variable name="auto-label-app" select="false()"/>
  <xsl:variable name="auto-label-boxed-text" select="false()"/>
  <xsl:variable name="auto-label-chem-struct-wrap" select="false()"/>
  <xsl:variable name="auto-label-disp-formula" select="false()"/>
  <xsl:variable name="auto-label-fig" select="false()"/>
  <xsl:variable name="auto-label-ref" select="not(//ref[label])"/>
  <!-- ref elements are labeled unless any ref already has a label -->
  
  <xsl:variable name="auto-label-statement" select="false()"/>
  <xsl:variable name="auto-label-supplementary"
    select="false()"/>
  <xsl:variable name="auto-label-table-wrap" select="false()"/>

<!--
  These variables assignments show how autolabeling can be 
  configured conditionally.
  For example: "label figures if no figures have labels" translates to
    "not(//fig[label])", which will resolve to Boolean true() when the set of
    all fig elements with labels is empty.
  
  <xsl:variable name="auto-label-app" select="not(//app[label])"/>
  <xsl:variable name="auto-label-boxed-text" select="not(//boxed-text[label])"/>
  <xsl:variable name="auto-label-chem-struct-wrap" select="not(//chem-struct-wrap[label])"/>
  <xsl:variable name="auto-label-disp-formula" select="not(//disp-formula[label])"/>
  <xsl:variable name="auto-label-fig" select="not(//fig[label])"/>
  <xsl:variable name="auto-label-ref" select="not(//ref[label])"/>
  <xsl:variable name="auto-label-statement" select="not(//statement[label])"/>
  <xsl:variable name="auto-label-supplementary"
    select="not(//supplementary-material[not(ancestor::front)][label])"/>
  <xsl:variable name="auto-label-table-wrap" select="not(//table-wrap[label])"/>
-->  

  <xsl:template mode="label" match="*" name="block-label">
    <xsl:param name="contents">
      <xsl:apply-templates select="." mode="label-text">
        <!-- place a warning for missing labels if this element is ever
             cross-referenced with an empty xref -->
        <xsl:with-param name="warning"
          select="boolean(key('xref-by-rid',@id)[not(normalize-space(string(.)))])"/>
      </xsl:apply-templates>
    </xsl:param>
    <xsl:if test="normalize-space(string($contents))">
      <!-- not to create an empty label. A plain div, not a heading:
           see the note on the "label" template -->
      <div class="label">
        <xsl:copy-of select="$contents"/>
      </div>
    </xsl:if>
  </xsl:template>


  <xsl:template mode="label" match="ref">
    <xsl:param name="contents">
      <xsl:apply-templates select="." mode="label-text"/>
    </xsl:param>
    <xsl:if test="normalize-space(string($contents))">
      <!-- we're already in a p -->
        <span class="label">
          <xsl:copy-of select="$contents"/>
        </span>
    </xsl:if>
  </xsl:template>

  
  <xsl:template match="app" mode="label-text">
    <xsl:param name="warning" select="true()"/>
    <!-- pass $warning in as false() if a warning string is not wanted
         (for example, if generating autonumbered labels) -->
    <xsl:call-template name="make-label-text">
      <xsl:with-param name="auto" select="$auto-label-app"/>
      <xsl:with-param name="warning" select="$warning"/>
      <!--
      Pass in the desired label if a label is to be autogenerated  
      <xsl:with-param name="auto-text">
        <xsl:text>Appendix </xsl:text>
        <xsl:number format="A"/>
      </xsl:with-param>-->
    </xsl:call-template>
  </xsl:template>
  

  <xsl:template match="boxed-text" mode="label-text">
    <xsl:param name="warning" select="true()"/>
    <!-- pass $warning in as false() if a warning string is not wanted
         (for example, if generating autonumbered labels) -->
    <xsl:call-template name="make-label-text">
      <xsl:with-param name="auto" select="$auto-label-boxed-text"/>
      <xsl:with-param name="warning" select="$warning"/>
      <xsl:with-param name="auto-text">
        <xsl:text>Box </xsl:text>
        <xsl:number level="any"/>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>

  
  <xsl:template match="disp-formula" mode="label-text">
    <xsl:param name="warning" select="true()"/>
    <!-- pass $warning in as false() if a warning string is not wanted
         (for example, if generating autonumbered labels) -->
    <xsl:call-template name="make-label-text">
      <xsl:with-param name="auto" select="$auto-label-disp-formula"/>
      <xsl:with-param name="warning" select="$warning"/>
      <xsl:with-param name="auto-text">
        <xsl:text>Formula </xsl:text>
        <xsl:number level="any"/>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="chem-struct-wrap | chem-struct-wrapper" mode="label-text">
    <xsl:param name="warning" select="true()"/>
    <!-- pass $warning in as false() if a warning string is not wanted
         (for example, if generating autonumbered labels) -->
    <xsl:call-template name="make-label-text">
      <xsl:with-param name="auto" select="$auto-label-chem-struct-wrap"/>
      <xsl:with-param name="warning" select="$warning"/>
      <xsl:with-param name="auto-text">
        <xsl:text>Formula (chemical) </xsl:text>
        <xsl:number level="any"/>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="fig" mode="label-text">
    <xsl:param name="warning" select="true()"/>
    <!-- pass $warning in as false() if a warning string is not wanted
         (for example, if generating autonumbered labels) -->
    <xsl:call-template name="make-label-text">
      <xsl:with-param name="auto" select="$auto-label-fig"/>
      <xsl:with-param name="warning" select="$warning"/>
      <xsl:with-param name="auto-text">
        <xsl:text>Figure </xsl:text>
        <xsl:number level="any"/>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="front//fn" mode="label-text">
    <xsl:param name="warning" select="boolean(key('xref-by-rid',@id))"/>
    <!-- pass $warning in as false() if a warning string is not wanted
         (for example, if generating autonumbered labels);
         by default, we get a warning only if we need a label for
         a cross-reference -->
    <!-- auto-number-fn is true only if (1) this fn is cross-referenced, and
         (2) there exists inside the front matter any fn elements with
         cross-references, but not labels or @symbols. -->
    <xsl:param name="auto-number-fn"
      select="boolean(key('xref-by-rid',parent::fn/@id)) and
      boolean(ancestor::front//fn[key('xref-by-rid',@id)][not(label|@symbol)])"/>
    <xsl:call-template name="make-label-text">
      <xsl:with-param name="auto" select="$auto-number-fn"/>
      <xsl:with-param name="warning" select="$warning"/>
      <xsl:with-param name="auto-text">
        <xsl:number level="any" count="fn" from="front" format="a"/>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>
  
  
  <xsl:template match="table-wrap//fn" mode="label-text">
    <xsl:param name="warning" select="boolean(key('xref-by-rid',@id))"/>
    <!-- pass $warning in as false() if a warning string is not wanted
         (for example, if generating autonumbered labels);
         by default, we get a warning only if we need a label for
         a cross-reference -->
    <xsl:param name="auto-number-fn"
      select="not(ancestor::table-wrap//fn/label | ancestor::table-wrap//fn/@symbol)"/>
    <xsl:call-template name="make-label-text">
      <xsl:with-param name="auto" select="$auto-number-fn"/>
      <xsl:with-param name="warning" select="$warning"/>
      <xsl:with-param name="auto-text">
        <xsl:text>[</xsl:text>
        <xsl:number level="any" count="fn" from="table-wrap" format="i"/>
        <xsl:text>]</xsl:text>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>
  
  
  <xsl:template match="fn" mode="label-text">
    <xsl:param name="warning" select="boolean(key('xref-by-rid',@id))"/>
    <!-- pass $warning in as false() if a warning string is not wanted
         (for example, if generating autonumbered labels);
         by default, we get a warning only if we need a label for
         a cross-reference -->
    <!-- autonumber all fn elements outside fn-group,
         front matter and table-wrap only if none of them 
         have labels or @symbols (to keep numbering
         orderly) -->
    <xsl:variable name="in-scope-notes"
      select="ancestor::article//fn[not(parent::fn-group
      | ancestor::front
      | ancestor::table-wrap)]"/>
    <xsl:variable name="auto-number-fn"
      select="not($in-scope-notes/label |
      $in-scope-notes/@symbol)"/>
    <xsl:call-template name="make-label-text">
      <xsl:with-param name="auto" select="$auto-number-fn"/>
      <xsl:with-param name="warning" select="$warning"/>
      <xsl:with-param name="auto-text">
        <xsl:text>[</xsl:text>
        <xsl:number level="any" count="fn[not(ancestor::front)]"
        from="article | sub-article | response"/>
        <xsl:text>]</xsl:text>
        <xsl:apply-templates select="@fn-type"/>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>

  <xsl:template match="fn/@fn-type[.='abbr']" priority="2">
    <span class="generated"> Abbreviation</span>
  </xsl:template>
  
  <xsl:template match="fn/@fn-type[.='com']" priority="2">
    <span class="generated"> Communicated by</span>
  </xsl:template>
  
  <xsl:template match="fn/@fn-type[.='con']" priority="2">
    <span class="generated"> Contributed by</span>
  </xsl:template>
  
  <xsl:template match="fn/@fn-type[.='conflict']" priority="2">
    <span class="generated"> Conflicts of interest</span>
  </xsl:template>
  
  <xsl:template match="fn/@fn-type[.='corresp']" priority="2">
    <span class="generated"> Corresponding author</span>
  </xsl:template>
  
  <xsl:template match="fn/@fn-type[.='current-aff']" priority="2">
    <span class="generated"> Current affiliation</span>
  </xsl:template>
  
  <xsl:template match="fn/@fn-type[.='deceased']" priority="2">
    <span class="generated"> Deceased</span>
  </xsl:template>
  
  <xsl:template match="fn/@fn-type[.='edited-by']" priority="2">
    <span class="generated"> Edited by</span>
  </xsl:template>
  
  <xsl:template match="fn/@fn-type[.='equal']" priority="2">
    <span class="generated"> Equal contributor</span>
  </xsl:template>
  
  <xsl:template match="fn/@fn-type[.='financial-disclosure']" priority="2">
    <span class="generated"> Financial disclosure</span>
  </xsl:template>
  
  <xsl:template match="fn/@fn-type[.='on-leave']" priority="2">
    <span class="generated"> On leave</span>
  </xsl:template>
  
  <xsl:template match="fn/@fn-type[.='other']" priority="2"/>
  
  <xsl:template match="fn/@fn-type[.='participating-researchers']" priority="2">
    <span class="generated"> Participating researcher</span>
  </xsl:template>
  
  <xsl:template match="fn/@fn-type[.='present-address']" priority="2">
    <span class="generated"> Current address</span>
  </xsl:template>
  
  <xsl:template match="fn/@fn-type[.='presented-at']" priority="2">
    <span class="generated"> Presented at</span>
  </xsl:template>
  
  <xsl:template match="fn/@fn-type[.='presented-by']" priority="2">
    <span class="generated"> Presented by</span>
  </xsl:template>
  
  <xsl:template match="fn/@fn-type[.='previously-at']" priority="2">
    <span class="generated"> Previously at</span>
  </xsl:template>
  
  <xsl:template match="fn/@fn-type[.='study-group-members']" priority="2">
    <span class="generated"> Study group member</span>
  </xsl:template>
  
  <xsl:template match="fn/@fn-type[.='supplementary-material']" priority="2">
    <span class="generated"> Supplementary material</span>
  </xsl:template>
  
  <xsl:template match="fn/@fn-type[.='supported-by']" priority="2">
    <span class="generated"> Supported by</span>
  </xsl:template>
  
  <xsl:template match="fn/@fn-type"/>
  
  
  <xsl:template match="ref" mode="label-text">
    <xsl:param name="warning" select="true()"/>
    <!-- pass $warning in as false() if a warning string is not wanted
         (for example, if generating autonumbered labels) -->
    <xsl:call-template name="make-label-text">
      <xsl:with-param name="auto" select="$auto-label-ref"/>
      <xsl:with-param name="warning" select="$warning"/>
      <xsl:with-param name="auto-text">
        <xsl:number level="any"/>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template match="statement" mode="label-text">
    <xsl:param name="warning" select="true()"/>
    <!-- pass $warning in as false() if a warning string is not wanted
         (for example, if generating autonumbered labels) -->
    <xsl:call-template name="make-label-text">
      <xsl:with-param name="auto" select="$auto-label-statement"/>
      <xsl:with-param name="warning" select="$warning"/>
      <xsl:with-param name="auto-text">
          <xsl:text>Statement </xsl:text>
        <xsl:number level="any"/>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>
  
 
  <xsl:template match="supplementary-material" mode="label-text">
    <xsl:param name="warning" select="true()"/>
    <!-- pass $warning in as false() if a warning string is not wanted
         (for example, if generating autonumbered labels) -->
    <xsl:call-template name="make-label-text">
      <xsl:with-param name="auto" select="$auto-label-supplementary"/>
      <xsl:with-param name="warning" select="$warning"/>
      <xsl:with-param name="auto-text">
          <xsl:text>Supplementary Material </xsl:text>
        <xsl:number level="any" format="A"
          count="supplementary-material[not(ancestor::front)]"/>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>
  
 
  <xsl:template match="table-wrap" mode="label-text">
    <xsl:param name="warning" select="true()"/>
    <!-- pass $warning in as false() if a warning string is not wanted
         (for example, if generating autonumbered labels) -->
    <xsl:call-template name="make-label-text">
      <xsl:with-param name="auto" select="$auto-label-table-wrap"/>
      <xsl:with-param name="warning" select="$warning"/>
      <xsl:with-param name="auto-text">
        <xsl:text>Table </xsl:text>
        <xsl:number level="any" format="I"/>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>
  
 
  <xsl:template match="*" mode="label-text">
    <xsl:param name="warning" select="true()"/>
    <!-- pass $warning in as false() if a warning string is not wanted
         (for example, if generating autonumbered labels) -->
    <xsl:call-template name="make-label-text">
      <xsl:with-param name="warning" select="$warning"/>
    </xsl:call-template>
  </xsl:template>
  
 
  <xsl:template match="label" mode="label-text">
    <xsl:apply-templates mode="inline-label-text"/>
  </xsl:template>
  
  
  <xsl:template match="text()" mode="inline-label-text">
    <!-- when displaying labels, space characters become non-breaking spaces -->
    <xsl:value-of select="translate(normalize-space(string(.)),' &#xA;&#x9;','&#xA0;&#xA0;&#xA0;')"/>
  </xsl:template>
  

<!-- ============================================================= -->
<!--  Writing a name                                               -->
<!-- ============================================================= -->

  <!-- Called when displaying structured names in metadata         -->

  <xsl:template match="name">
    <xsl:apply-templates select="prefix" mode="inline-name"/>
    <xsl:apply-templates select="surname[../@name-style='eastern']"
      mode="inline-name"/>
    <xsl:apply-templates select="given-names" mode="inline-name"/>
    <xsl:apply-templates select="surname[not(../@name-style='eastern')]"
      mode="inline-name"/>
    <xsl:apply-templates select="suffix" mode="inline-name"/>
  </xsl:template>


  <xsl:template match="prefix" mode="inline-name">
    <xsl:apply-templates/>
    <xsl:if test="../surname | ../given-names | ../suffix">
      <xsl:text> </xsl:text>
    </xsl:if>
  </xsl:template>


  <xsl:template match="given-names" mode="inline-name">
    <xsl:apply-templates/>
    <xsl:if test="../surname[not(../@name-style='eastern')] | ../suffix">
      <xsl:text> </xsl:text>
    </xsl:if>
  </xsl:template>


  <xsl:template match="contrib/name/surname" mode="inline-name">
    <xsl:apply-templates/>
    <xsl:if test="../given-names[../@name-style='eastern'] | ../suffix">
      <xsl:text> </xsl:text>
    </xsl:if>
  </xsl:template>


  <xsl:template match="surname" mode="inline-name">
    <xsl:apply-templates/>
    <xsl:if test="../given-names[../@name-style='eastern'] | ../suffix">
      <xsl:text> </xsl:text>
    </xsl:if>
  </xsl:template>


  <xsl:template match="suffix" mode="inline-name">
    <xsl:apply-templates/>
  </xsl:template>

  
  <!-- string-name elements are written as is -->
  
  <xsl:template match="string-name">
    <xsl:apply-templates/>
  </xsl:template>
  
  
  <xsl:template match="string-name/*">
    <xsl:apply-templates/>
  </xsl:template>
  
  
<!-- ============================================================= -->
<!--  UTILITY TEMPLATES                                           -->
<!-- ============================================================= -->


  <xsl:template name="append-pub-type">
    <!-- adds a value mapped for @pub-type, enclosed in parenthesis,
         to a string -->
    <xsl:for-each select="@pub-type">
      <xsl:text> (</xsl:text>
      <span class="data">
        <xsl:choose>
          <xsl:when test=".='epub'">electronic</xsl:when>
          <xsl:when test=".='ppub'">print</xsl:when>
          <xsl:when test=".='epub-ppub'">print and electronic</xsl:when>
          <xsl:when test=".='epreprint'">electronic preprint</xsl:when>
          <xsl:when test=".='ppreprint'">print preprint</xsl:when>
          <xsl:when test=".='ecorrected'">corrected, electronic</xsl:when>
          <xsl:when test=".='pcorrected'">corrected, print</xsl:when>
          <xsl:when test=".='eretracted'">retracted, electronic</xsl:when>
          <xsl:when test=".='pretracted'">retracted, print</xsl:when>
          <xsl:otherwise>
            <xsl:value-of select="."/>
          </xsl:otherwise>
        </xsl:choose>
      </span>
      <xsl:text>)</xsl:text>
    </xsl:for-each>
  </xsl:template>


  <xsl:template name="metadata-labeled-entry">
    <xsl:param name="label"/>
    <xsl:param name="contents">
      <xsl:apply-templates/>
    </xsl:param>
    <xsl:call-template name="metadata-entry">
      <xsl:with-param name="contents">
        <xsl:if test="normalize-space(string($label))">
          <span class="generated">
            <xsl:copy-of select="$label"/>
            <xsl:text>: </xsl:text>
          </span>
        </xsl:if>
        <xsl:copy-of select="$contents"/>
      </xsl:with-param>
    </xsl:call-template>
  </xsl:template>


  <xsl:template name="metadata-entry">
    <xsl:param name="contents">
      <xsl:apply-templates/>
    </xsl:param>
    <p class="metadata-entry">
      <xsl:copy-of select="$contents"/>
    </p>
  </xsl:template>


  <xsl:template name="metadata-area">
    <xsl:param name="label"/>
    <xsl:param name="contents">
      <xsl:apply-templates/>
    </xsl:param>
    <div class="metadata-area">
      <xsl:if test="normalize-space(string($label))">
        <xsl:call-template name="metadata-labeled-entry">
          <xsl:with-param name="label">
            <xsl:copy-of select="$label"/>
          </xsl:with-param>
          <xsl:with-param name="contents"/>
        </xsl:call-template>
      </xsl:if>
      <div class="metadata-chunk">
        <xsl:copy-of select="$contents"/>
      </div>
    </div>
  </xsl:template>


  <xsl:template name="make-label-text">
    <xsl:param name="auto" select="false()"/>
    <xsl:param name="warning" select="false()"/>
    <xsl:param name="auto-text"/>
    <xsl:choose>
      <xsl:when test="$auto">
        <span class="generated">
          <xsl:copy-of select="$auto-text"/>
        </span>
      </xsl:when>
      <xsl:otherwise>
        <xsl:apply-templates mode="label-text"
          select="label | @symbol"/>
        <xsl:if test="$warning and not(label|@symbol)">
          <span class="warning">
            <xsl:text>{ label</xsl:text>
            <xsl:if test="self::fn"> (or @symbol)</xsl:if>
            <xsl:text> needed for </xsl:text>
            <xsl:value-of select="local-name()"/>
            <xsl:for-each select="@id">
              <xsl:text>[@id='</xsl:text>
              <xsl:value-of select="."/>
              <xsl:text>']</xsl:text>
            </xsl:for-each>
            <xsl:text> }</xsl:text>
          </span>
        </xsl:if>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>


  <xsl:template name="assign-id">
    <xsl:variable name="id">
      <xsl:apply-templates select="." mode="id"/>
    </xsl:variable>
    <xsl:attribute name="id">
      <xsl:value-of select="$id"/>
    </xsl:attribute>
  </xsl:template>


  <xsl:template name="assign-src">
    <xsl:for-each select="@xlink:href">
      <xsl:attribute name="src">
        <xsl:value-of select="."/>
      </xsl:attribute>
    </xsl:for-each>
  </xsl:template>


  <xsl:template name="assign-href">
    <xsl:for-each select="@xlink:href">
      <xsl:attribute name="href">
        <xsl:value-of select="."/>
      </xsl:attribute>
    </xsl:for-each>
  </xsl:template>


  <xsl:template name="named-anchor">
    <!-- generates an HTML named anchor -->
    <xsl:variable name="id">
      <xsl:choose>
        <xsl:when test="@id">
          <!-- if we have an @id, we use it -->
          <xsl:value-of select="@id"/>
        </xsl:when>
        <xsl:when test="not(preceding-sibling::*) and
          (parent::alternatives | parent::name-alternatives |
           parent::citation-alternatives | parent::collab-alternatives |
           parent::aff-alternatives)/@id">
          <!-- if not, and we are first among our siblings inside one of
               several 'alternatives' wrappers, we use its @id if available -->
          <xsl:value-of select="(parent::alternatives | parent::name-alternatives |
            parent::citation-alternatives | parent::collab-alternatives |
            parent::aff-alternatives)/@id"/>
        </xsl:when>
        <xsl:otherwise>
          <!-- otherwise we simply generate an ID -->
          <xsl:value-of select="generate-id(.)"/>
        </xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    <a id="{$id}">
      <xsl:comment> named anchor </xsl:comment>
    </a>
  </xsl:template>


<!-- ============================================================= -->
<!--  Process warnings                                             -->
<!-- ============================================================= -->
<!-- Generates a list of warnings to be reported due to processing
     anomalies. -->

  <xsl:template name="process-warnings">
    <!-- Only generate the warnings if set to $verbose -->
    <xsl:if test="$verbose">
    <!-- returns an RTF containing all the warnings -->
    <xsl:variable name="xref-warnings">
      <xsl:for-each select="//xref[not(normalize-space(string(.)))]">
        <xsl:variable name="target-label">
          <xsl:apply-templates select="key('element-by-id',@rid)"
            mode="label-text">
            <xsl:with-param name="warning" select="false()"/>
          </xsl:apply-templates>
        </xsl:variable>
        <xsl:if test="not(normalize-space(string($target-label))) and
          generate-id(.) = generate-id(key('xref-by-rid',@rid)[1])">
          <!-- if we failed to get a label with no warning, and
               this is the first cross-reference to this target
               we ask again to get the warning -->
          <li>
            <xsl:apply-templates select="key('element-by-id',@rid)"
              mode="label-text">
              <xsl:with-param name="warning" select="true()"/>
            </xsl:apply-templates>
          </li>
        </xsl:if>
      </xsl:for-each>
    </xsl:variable>

    <xsl:if test="normalize-space(string($xref-warnings))">
      <h4>Elements are cross-referenced without labels.</h4>
      <p>Either the element should be provided a label, or their cross-reference(s) should
        have literal text content.</p>
      <ul>
        <xsl:copy-of select="$xref-warnings"/>
      </ul>
    </xsl:if>
    
    
    <xsl:variable name="alternatives-warnings">
      <!-- for reporting any element with a @specific-use different
           from a sibling -->
      <xsl:for-each select="//*[@specific-use != ../*/@specific-use]/..">
        <li>
          <xsl:text>In </xsl:text>
          <xsl:apply-templates select="." mode="xpath"/>
          <ul>
            <xsl:for-each select="*[@specific-use != ../*/@specific-use]">
              <li>
                <xsl:apply-templates select="." mode="pattern"/>
              </li>
            </xsl:for-each>
          </ul>
          <!--<xsl:text>: </xsl:text>
          <xsl:call-template name="list-elements">
            <xsl:with-param name="elements" select="*[@specific-use]"/>
          </xsl:call-template>-->
        </li>
      </xsl:for-each>
    </xsl:variable>
    
    <xsl:if test="normalize-space(string($alternatives-warnings))">
      <h4>Elements with different 'specific-use' assignments appearing together</h4>
      <ul>
        <xsl:copy-of select="$alternatives-warnings"/>
      </ul>
    </xsl:if>
    </xsl:if>
    
  </xsl:template>
  
<!-- ============================================================= -->
<!--  id mode                                                      -->
<!-- ============================================================= -->
<!-- An id can be derived for any element. If an @id is given,
     it is presumed unique and copied. If not, one is generated.   -->

  <xsl:template match="*" mode="id">
    <xsl:value-of select="@id"/>
    <xsl:if test="not(@id)">
      <xsl:value-of select="generate-id(.)"/>
    </xsl:if>
  </xsl:template>


  <xsl:template match="article | sub-article | response" mode="id">
    <xsl:value-of select="@id"/>
    <xsl:if test="not(@id)">
      <xsl:value-of select="local-name()"/>
      <xsl:number from="article" level="multiple"
        count="article | sub-article | response" format="1-1"/>
    </xsl:if>
  </xsl:template>


<!-- ============================================================= -->
<!--  "format-date"                                                -->
<!-- ============================================================= -->
<!-- Maps a structured date element to a string -->

  <xsl:template name="format-date">
    <!-- formats date in DD Month YYYY format -->
    <!-- context must be 'date', with content model:
         (((day?, month?) | season)?, year) -->
    <xsl:for-each select="day|month|season">
      <xsl:apply-templates select="." mode="map"/>
      <xsl:text> </xsl:text>
    </xsl:for-each>
    <xsl:apply-templates select="year" mode="map"/>
  </xsl:template>


  <xsl:template match="day | season | year" mode="map">
    <xsl:apply-templates/>
  </xsl:template>


  <xsl:template match="month" mode="map">
    <!-- maps numeric values to English months -->
    <xsl:choose>
      <xsl:when test="number() = 1">January</xsl:when>
      <xsl:when test="number() = 2">February</xsl:when>
      <xsl:when test="number() = 3">March</xsl:when>
      <xsl:when test="number() = 4">April</xsl:when>
      <xsl:when test="number() = 5">May</xsl:when>
      <xsl:when test="number() = 6">June</xsl:when>
      <xsl:when test="number() = 7">July</xsl:when>
      <xsl:when test="number() = 8">August</xsl:when>
      <xsl:when test="number() = 9">September</xsl:when>
      <xsl:when test="number() = 10">October</xsl:when>
      <xsl:when test="number() = 11">November</xsl:when>
      <xsl:when test="number() = 12">December</xsl:when>
      <xsl:otherwise>
        <xsl:apply-templates/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>
  

<!-- ============================================================= -->
<!--  "author-string" writes authors' names in sequence            -->
<!-- ============================================================= -->

  <xsl:template name="author-string">
    <!-- In JATS, surname and given-names are children of <name>, not of
         <contrib>. Selecting contrib/surname matched nothing, so the browser
         tab title lost its author prefix entirely. -->
    <!-- authors only: issue editors sit in their own contrib-group and
         must not end up in the article's byline. -->
    <xsl:variable name="all-contribs"
      select="/article/front/article-meta/contrib-group[not(@content-type)]/contrib[
                not(@contrib-type) or @contrib-type='author']/name/surname |
              /article/front/article-meta/contrib-group[not(@content-type)]/contrib[
                not(@contrib-type) or @contrib-type='author']/collab"/>
   <xsl:for-each select="$all-contribs">
      <xsl:if test="count($all-contribs) &gt; 1">
        <xsl:if test="position() &gt; 1">
          <xsl:if test="count($all-contribs) &gt; 2">,</xsl:if>
          <xsl:text> </xsl:text>
        </xsl:if>
        <xsl:if test="position() = count($all-contribs)">and </xsl:if>
      </xsl:if>
      <xsl:value-of select="."/>
    </xsl:for-each>
  </xsl:template>
  

<!-- ============================================================= -->
<!--  Footer branding                                              -->
<!-- ============================================================= -->

  <!--  The galley's only script                               -->
 
  <xsl:template name="galley-script">
    <script type="text/javascript"><![CDATA[
(function () {
  "use strict";

  /* ---- copy to clipboard, with a fallback for insecure contexts ---- */
  function copyText(text, button, label) {
    function done(ok) {
      button.textContent = ok ? "Copied" : "Copy failed";
      window.setTimeout(function () { button.textContent = label; }, 2000);
    }
    function legacy() {
      var ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.top = "-1000px";
      document.body.appendChild(ta);
      ta.select();
      var ok = false;
      try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
      document.body.removeChild(ta);
      done(ok);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { done(true); }, legacy);
    } else {
      legacy();
    }
  }

  /* ---- How to cite: three styles behind three tabs ----------------- */
  var widget = document.querySelector(".cite-widget");
  if (widget) {
    var tabs = Array.prototype.slice.call(widget.querySelectorAll(".cite-tab"));
    var panels = Array.prototype.slice.call(widget.querySelectorAll(".cite-panel"));

    if (tabs.length === panels.length && tabs.length > 0) {
      /* Only now does the stylesheet start hiding panels. Until this class
         is set, every citation is on the page, which is what a reader with
         no JavaScript sees. */
      widget.className += " js-cite";

      var show = function (i) {
        tabs.forEach(function (t, n) {
          var on = (n === i);
          t.setAttribute("aria-selected", on ? "true" : "false");
          t.tabIndex = on ? 0 : -1;
          if (on) { t.classList.add("is-current"); }
          else { t.classList.remove("is-current"); }
        });
        panels.forEach(function (p, n) {
          if (n === i) { p.classList.add("is-current"); }
          else { p.classList.remove("is-current"); }
        });
      };

      tabs.forEach(function (tab, i) {
        tab.addEventListener("click", function () { show(i); });
        tab.addEventListener("keydown", function (e) {
          var step = 0;
          if (e.key === "ArrowRight") { step = 1; }
          if (e.key === "ArrowLeft") { step = -1; }
          if (step === 0) { return; }
          e.preventDefault();
          var n = (i + step + tabs.length) % tabs.length;
          show(n);
          tabs[n].focus();
        });
      });
      show(0);

      var wrap = widget.querySelector(".cite-copy-wrap");
      if (wrap) {
        var copyBtn = document.createElement("button");
        copyBtn.type = "button";
        copyBtn.className = "cite-copy";
        copyBtn.textContent = "Copy citation";
        copyBtn.addEventListener("click", function () {
          var current = widget.querySelector(".cite-panel.is-current .cite-text");
          if (!current) { return; }
          copyText(current.textContent.replace(/\s+/g, " ").trim(),
                   copyBtn, "Copy citation");
        });
        wrap.appendChild(copyBtn);
      }
    }
  }

  /* ---- Share ------------------------------------------------------- */
  var share = document.querySelector(".action-share .action-panel");
  if (share) {
    var host = share.querySelector(".share-actions");
    /* The galley is often inside an OJS iframe, where location.href is the
       galley file rather than the article. The DOI written into the page is
       the address worth sending someone, so it is preferred; this is only
       the fallback for an article that has no DOI yet. */
    var url = share.getAttribute("data-share-url") || window.location.href;
    var title = share.getAttribute("data-share-title") || document.title;

    if (host) {
      var copyLink = document.createElement("button");
      copyLink.type = "button";
      copyLink.className = "share-btn";
      copyLink.textContent = "Copy link";
      copyLink.addEventListener("click", function () {
        copyText(url, copyLink, "Copy link");
      });
      host.appendChild(copyLink);

      /* The operating system's own share sheet where there is one. */
      if (navigator.share) {
        var native = document.createElement("button");
        native.type = "button";
        native.className = "share-btn";
        native.textContent = "Share…";
        native.addEventListener("click", function () {
          navigator.share({ title: title, url: url }).catch(function () {});
        });
        host.appendChild(native);
      }

      var targets = [
        ["Email", "mailto:?subject=" + encodeURIComponent(title) +
                  "&body=" + encodeURIComponent(title + "\n" + url)],
        ["Facebook", "https://www.facebook.com/sharer/sharer.php?u=" +
                 encodeURIComponent(url)],
        ["Bluesky", "https://bsky.app/intent/compose?text=" +
                    encodeURIComponent(title + " " + url)],
        ["LinkedIn", "https://www.linkedin.com/sharing/share-offsite/?url=" +
                     encodeURIComponent(url)]
      ];
      targets.forEach(function (t) {
        var a = document.createElement("a");
        a.className = "share-btn";
        a.href = t[1];
        a.textContent = t[0];
        if (t[1].indexOf("mailto:") !== 0) {
          a.target = "_blank";
          a.rel = "noopener noreferrer";
        }
        host.appendChild(a);
      });
    }
  }

  /* Export references  */
  function refText(li) {
    var box = li.querySelector(".mixed-citation, .citation, .element-citation") || li;
    var clone = box.cloneNode(true);
    Array.prototype.forEach.call(clone.querySelectorAll("a.xref"), function (a) {
      if (a.textContent.trim() === "↩") { a.parentNode.removeChild(a); }
    });
    return clone.textContent.replace(/\s+/g, " ").replace(/\s*↩\s*$/, "").trim();
  }
  function refPeople(li, attr) {
    var v = li.getAttribute(attr);
    return v ? v.split("|").filter(function (s) { return s.trim(); }) : [];
  }
  function refData(li) {
    var d = {};
    ["type", "title", "source", "series", "year", "volume", "issue", "fpage",
     "lpage", "publisher", "place", "isbn", "doi", "url"].forEach(function (k) {
      d[k] = li.getAttribute("data-" + k) || "";
    });
    d.authors = refPeople(li, "data-authors");
    d.editors = refPeople(li, "data-editors");
    d.text = refText(li);
    return d;
  }

  var RIS_TYPES = { journal: "JOUR", book: "BOOK", chapter: "CHAP",
    thesis: "THES", webpage: "ELEC", web: "ELEC", website: "ELEC",
    newspaper: "NEWS", magazine: "MGZN", report: "RPRT", confproc: "CPAPER",
    conference: "CPAPER", film: "MPCT", video: "VIDEO", map: "MAP",
    archive: "UNPB", manuscript: "UNPB" };

  function toRIS(refs) {
    return refs.map(function (d) {
      var lines = [];
      function add(tag, v) { if (v) { lines.push(tag + "  - " + v); } }
      var structured = d.type || d.title || d.source || d.authors.length;
      add("TY", RIS_TYPES[d.type] || "GEN");
      d.authors.forEach(function (a) { add("AU", a); });
      d.editors.forEach(function (a) { add("ED", a); });
      if (d.title) {
        add("TI", d.title);
        add("T2", d.source);
      } else {
        add("TI", d.source || (structured ? "" : d.text));
      }
      add("T3", d.series);
      add("PY", d.year);
      add("VL", d.volume);
      add("IS", d.issue);
      add("SP", d.fpage);
      add("EP", d.lpage);
      add("PB", d.publisher);
      add("CY", d.place);
      add("SN", d.isbn);
      add("DO", d.doi);
      add("UR", d.url || (d.doi ? "https://doi.org/" + d.doi : ""));
      if (!structured) { add("N1", d.text); }
      lines.push("ER  - ");
      return lines.join("\r\n");
    }).join("\r\n\r\n") + "\r\n";
  }

  var BIB_TYPES = { journal: "article", newspaper: "article", magazine: "article",
    book: "book", chapter: "incollection", thesis: "phdthesis",
    report: "techreport", confproc: "inproceedings", conference: "inproceedings" };

  function bibEsc(s) {
    return String(s).replace(/([&%$#_])/g, "\\$1");
  }
  function toBibTeX(refs) {
    var used = {};
    return refs.map(function (d) {
      var first = (d.authors[0] || d.editors[0] || d.title || d.source || "ref").split(",")[0];
      var base = (first.normalize ? first.normalize("NFD") : first)
        .replace(/[^A-Za-z0-9]/g, "").toLowerCase() || "ref";
      base += (d.year.match(/\d{4}/) || [""])[0];
      var key = base, n = 0;
      while (used[key]) { n += 1; key = base + String.fromCharCode(96 + n); }
      used[key] = true;
      var type = BIB_TYPES[d.type] || "misc";
      var f = [];
      function add(name, v, braces) {
        if (v) { f.push("  " + name + " = {" + (braces ? "{" + bibEsc(v) + "}" : bibEsc(v)) + "}"); }
      }
      /* an organization (no comma) is braced so BibTeX keeps it whole */
      function people(list) {
        return list.map(function (p) {
          return p.indexOf(",") < 0 && p.indexOf(" ") > 0 ? "{" + p + "}" : p;
        }).join(" and ");
      }
      add("author", people(d.authors));
      add("editor", people(d.editors));
      if (d.title) {
        add("title", d.title, true);
        add(type === "article" ? "journal" : "booktitle", d.source, true);
      } else {
        add("title", d.source, true);
      }
      add("series", d.series);
      add("year", d.year);
      add("volume", d.volume);
      add("number", d.issue);
      add("pages", d.fpage && d.lpage ? d.fpage + "--" + d.lpage : d.fpage);
      add(type === "phdthesis" ? "school" : "publisher", d.publisher);
      add("address", d.place);
      add("isbn", d.isbn);
      if (d.doi) { f.push("  doi = {" + d.doi + "}"); }
      if (d.url) { f.push("  url = {" + d.url + "}"); }
      if (!d.title && !d.source) { add("note", d.text); }
      return "@" + type + "{" + key + ",\n" + f.join(",\n") + "\n}";
    }).join("\n\n") + "\n";
  }

  function toText(groups) {
    return groups.map(function (g) {
      var body = g.refs.map(function (d) { return d.text; }).join("\n\n");
      return g.title ? g.title + "\n\n" + body : body;
    }).join("\n\n\n") + "\n";
  }

  function saveFile(text, name, type) {
    var blob = new Blob([text], { type: type + ";charset=utf-8" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    window.setTimeout(function () {
      URL.revokeObjectURL(a.href);
      document.body.removeChild(a);
    }, 1000);
  }

  var fileBase = (document.title || "references")
    .split(/\s[|–—-]\s/)[0]
    .replace(/[^A-Za-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 60)
    .toLowerCase() || "references";

  function headText(section) {
    var h = section.querySelector("h1, h2, h3, h4, h5, h6, .main-title");
    return h ? h.textContent.replace(/\s+/g, " ").trim() : "";
  }

  /* A note as text: "1. Harold A. Innis, ...", without the return arrow. */
  function noteText(el) {
    var clone = el.cloneNode(true);
    Array.prototype.forEach.call(clone.querySelectorAll("a.fn-return, a.xref"), function (a) {
      if (a.textContent.trim() === "\u21A9") { a.parentNode.removeChild(a); }
    });
    return clone.textContent.replace(/\s+/g, " ").replace(/\s*\u21A9\s*$/, "").trim()
      .replace(/^(\d+)\.?\s+/, "$1. ");
  }
  function noteData(el) { return { text: noteText(el) }; }

  /* kind "refs" offers RIS, BibTeX, text and copy; kind "notes" only text
     and copy, since a note is prose (often several sources and comment)
     with no fields a reference manager could fill in. */
  function buildExportBar(host, before, sections, kind) {
    var notes = (kind === "notes");
    var noun = notes ? "notes" : "references";
    var bar = document.createElement("div");
    bar.className = "ref-export";
    bar.setAttribute("role", "group");
    bar.setAttribute("aria-label", "Export " + noun);

    var label = document.createElement("span");
    label.className = "ref-export-label";
    label.textContent = "Export " + noun;
    bar.appendChild(label);

    var pick = null;
    if (sections.length > 1) {
      pick = document.createElement("select");
      pick.className = "ref-export-pick";
      pick.setAttribute("aria-label", "Which section to export");
      var all = document.createElement("option");
      all.value = "";
      all.textContent = "All sections";
      pick.appendChild(all);
      sections.forEach(function (s, i) {
        var o = document.createElement("option");
        o.value = String(i);
        o.textContent = s.title || ("Section " + (i + 1));
        pick.appendChild(o);
      });
      bar.appendChild(pick);
    }

    function chosen() {
      var list = (pick && pick.value !== "") ? [sections[+pick.value]] : sections;
      return list.map(function (s) {
        return { title: sections.length > 1 ? s.title : "",
                 refs: s.items.map(notes ? noteData : refData) };
      });
    }
    function flat() {
      return chosen().reduce(function (acc, g) { return acc.concat(g.refs); }, []);
    }
    function suffix() {
      if (!pick || pick.value === "") { return ""; }
      var t = sections[+pick.value].title || ("section-" + (+pick.value + 1));
      return "-" + t.replace(/[^A-Za-z0-9]+/g, "-").replace(/^-|-$/g, "").toLowerCase();
    }

    var buttons = notes ? [] : [
      ["RIS", "For Zotero, EndNote, Mendeley and most reference managers", function () {
        saveFile(toRIS(flat()), fileBase + "-references" + suffix() + ".ris",
                 "application/x-research-info-systems");
      }],
      ["BibTeX", "For LaTeX, JabRef and BibDesk", function () {
        saveFile(toBibTeX(flat()), fileBase + "-references" + suffix() + ".bib",
                 "application/x-bibtex");
      }]
    ];
    buttons.push(["Text", "The " + noun + " as printed, as a plain text file", function () {
      saveFile(toText(chosen()), fileBase + "-" + noun + suffix() + ".txt", "text/plain");
    }]);
    buttons.forEach(function (b) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "share-btn";
      btn.textContent = b[0];
      btn.title = b[1];
      btn.addEventListener("click", b[2]);
      bar.appendChild(btn);
    });
    var copy = document.createElement("button");
    copy.type = "button";
    copy.className = "share-btn";
    copy.textContent = "Copy";
    copy.title = "Copy the " + noun + " as printed";
    copy.addEventListener("click", function () {
      copyText(toText(chosen()), copy, "Copy");
    });
    bar.appendChild(copy);

    host.insertBefore(bar, before);
  }

  if (window.Blob && window.URL && URL.createObjectURL) {
    /* the Bibliography of British Columbia: one bar for all its sections */
    Array.prototype.forEach.call(document.querySelectorAll(".bibliography-of-bc"), function (bib) {
      var sections = Array.prototype.slice.call(bib.querySelectorAll(".bib-section"))
        .map(function (s) {
          return { title: headText(s), items: Array.prototype.slice.call(s.querySelectorAll("li.ref-entry")) };
        })
        .filter(function (s) { return s.items.length; });
      var first = bib.querySelector(".bib-section");
      if (sections.length && first) { buildExportBar(first.parentNode, first, sections); }
    });
    /* every other reference list: the outermost one, items and all */
    Array.prototype.forEach.call(document.querySelectorAll(".ref-list"), function (list) {
      if (list.closest(".bibliography-of-bc")) { return; }
      if (list.parentNode.closest && list.parentNode.closest(".ref-list")) { return; }
      var items = Array.prototype.slice.call(list.querySelectorAll("li.ref-entry"));
      var firstList = list.querySelector("ul.ref-list-items");
      if (!items.length || !firstList) { return; }
      buildExportBar(firstList.parentNode, firstList, [{ title: "", items: items }]);
    });
    /* notes: endnote paragraphs (Lens) or footnote blocks (archival), one
       bar per run of them; notes under a table belong to the table */
    var noteGroups = [];
    Array.prototype.forEach.call(document.querySelectorAll("p.endnote, div.footnote"), function (n) {
      if (n.closest(".table-wrap, .table-wrap-foot")) { return; }
      var g = noteGroups.filter(function (x) { return x.parent === n.parentNode; })[0];
      if (!g) { g = { parent: n.parentNode, items: [] }; noteGroups.push(g); }
      g.items.push(n);
    });
    noteGroups.forEach(function (g) {
      buildExportBar(g.parent, g.items[0], [{ title: "", items: g.items }], "notes");
    });
  }

  /* ---- Only one panel open at a time -------------------------------
     Named "disclosures", not "panels": var is function-scoped, so a second
     "var panels" here would be the SAME variable the citation tabs close
     over, and clicking a tab would start moving the current-tab class onto
     these <details> elements instead. */
  var disclosures = Array.prototype.slice.call(
    document.querySelectorAll(".sidebar-actions .action-details"));
  disclosures.forEach(function (d) {
    d.addEventListener("toggle", function () {
      if (!d.open) { return; }
      disclosures.forEach(function (other) {
        if (other !== d) { other.open = false; }
      });
    });
  });
}());
]]></script>
  </xsl:template>


  <xsl:template name="footer-branding">
    <!-- The upstream "generated by ..." credit is not wanted on a published
         galley. Emitting nothing is cleaner than emitting it and hiding it
         with CSS, which left a stray rule and leaked the XSLT engine name
         into the page source. -->
    <div class="branding">
    </div>
  </xsl:template>


  <!-- ============================================================= -->
  <!--  Utility templates for generating warnings and reports        -->
  <!-- ============================================================= -->
  
<!--  <xsl:template name="report-warning">
    <xsl:param name="when" select="false()"/>
    <xsl:param name="msg"/>
    <xsl:if test="$verbose and $when">
      <xsl:message>
        <xsl:copy-of select="$msg"/>
      </xsl:message>
    </xsl:if>
  </xsl:template>-->
  
  
  <!--<xsl:template name="list-elements">
    <xsl:param name="elements" select="/.."/>
    <xsl:if test="$elements">
      <ol>
        <xsl:for-each select="*">
          <li>
            <xsl:apply-templates select="." mode="element-pattern"/>
          </li>
        </xsl:for-each>
      </ol>
    </xsl:if>
  </xsl:template>-->


  <xsl:template match="*" mode="pattern">
    <xsl:value-of select="name(.)"/>
    <xsl:for-each select="@*">
      <xsl:text>[@</xsl:text>
      <xsl:value-of select="name()"/>
      <xsl:text>='</xsl:text>
      <xsl:value-of select="."/>
      <xsl:text>']</xsl:text>
    </xsl:for-each>
  </xsl:template>


  <xsl:template match="node()" mode="xpath">
    <xsl:apply-templates mode="xpath" select=".."/>
    <xsl:apply-templates mode="xpath-step" select="."/>
  </xsl:template>


  <xsl:template match="/" mode="xpath"/>


  <xsl:template match="*" mode="xpath-step">
    <xsl:variable name="name" select="name(.)"/>
    <xsl:text>/</xsl:text>
    <xsl:value-of select="$name"/>
    <xsl:if test="count(../*[name(.) = $name]) > 1">
      <xsl:text>[</xsl:text>
      <xsl:value-of select="count(.|preceding-sibling::*[name(.) = $name])"/>
      <xsl:text>]</xsl:text>
    </xsl:if>
  </xsl:template>


  <xsl:template match="@*" mode="xpath-step">
    <xsl:text>/@</xsl:text>
    <xsl:value-of select="name(.)"/>
  </xsl:template>


  <xsl:template match="comment()" mode="xpath-step">
    <xsl:text>/comment()</xsl:text>
    <xsl:if test="count(../comment()) > 1">
      <xsl:text>[</xsl:text>
      <xsl:value-of select="count(.|preceding-sibling::comment())"/>
      <xsl:text>]</xsl:text>
    </xsl:if>
  </xsl:template>


  <xsl:template match="processing-instruction()" mode="xpath-step">
    <xsl:text>/processing-instruction()</xsl:text>
    <xsl:if test="count(../processing-instruction()) > 1">
      <xsl:text>[</xsl:text>
      <xsl:value-of select="count(.|preceding-sibling::processing-instruction())"/>
      <xsl:text>]</xsl:text>
    </xsl:if>
  </xsl:template>


  <xsl:template match="text()" mode="xpath-step">
    <xsl:text>/text()</xsl:text>
    <xsl:if test="count(../text()) > 1">
      <xsl:text>[</xsl:text>
      <xsl:value-of select="count(.|preceding-sibling::text())"/>
      <xsl:text>]</xsl:text>
    </xsl:if>
  </xsl:template>


<!-- ============================================================= -->
<!--  End stylesheet                                               -->
<!-- ============================================================= -->

</xsl:stylesheet>