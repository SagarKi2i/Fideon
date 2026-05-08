import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { 
  CheckCircle2, 
  AlertTriangle, 
  DollarSign,
  Shield,
  TrendingUp,
  TrendingDown,
  Award,
  Zap,
  ThumbsUp,
  Target,
  BarChart3,
  Clock
} from "lucide-react";

interface CarrierQuote {
  carrier: string;
  logo: string;
  premium: number;
  coverage: string;
  deductible: number;
  status: "pending" | "fetching" | "complete" | "error";
  features: string[];
  rating?: number;
  claimsScore?: number;
  financialStrength?: string;
}

interface QuoteComparisonAnalysisProps {
  readonly quotes: CarrierQuote[];
}

export default function QuoteComparisonAnalysis({ quotes }: QuoteComparisonAnalysisProps) {
  const completedQuotes = quotes.filter((q: any) => q.status === "complete");
  
  if (completedQuotes.length === 0) return null;

  // Calculate analytics
  const premiums = completedQuotes.map((q: any) => q.premium);
  const lowestPremium = Math.min(...premiums);
  const highestPremium = Math.max(...premiums);
  const avgPremium = Math.round(premiums.reduce((a: any, b: any) => a + b, 0) / premiums.length);
  const potentialSavings = highestPremium - lowestPremium;

  // Find best options
  const lowestPremiumCarrier = completedQuotes.find((q: any) => q.premium === lowestPremium);
  const lowestDeductibleCarrier = completedQuotes.reduce((a: any, b: any) => a.deductible < b.deductible ? a : b, completedQuotes[0]!);
  const bestValueCarrier = completedQuotes.reduce((a: any, b: any) => {
    const aScore = (a.premium / 100) + (a.deductible / 50);
    const bScore = (b.premium / 100) + (b.deductible / 50);
    return aScore < bScore ? a : b;
  }, completedQuotes[0]!);

  // Sort by premium for ranking
  const sortedByPremium = [...completedQuotes].sort((a, b) => a.premium - b.premium);

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="bg-gradient-to-br from-green-500/10 to-green-600/5 border-green-500/20">
          <CardContent className="pt-4">
            <div className="flex items-center gap-2 mb-2">
              <DollarSign className="h-4 w-4 text-green-600" />
              <span className="text-xs font-medium text-green-600">Lowest Premium</span>
            </div>
            <p className="text-2xl font-bold text-foreground">${lowestPremium.toLocaleString()}</p>
            <p className="text-xs text-muted-foreground">{lowestPremiumCarrier?.carrier}</p>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-blue-500/10 to-blue-600/5 border-blue-500/20">
          <CardContent className="pt-4">
            <div className="flex items-center gap-2 mb-2">
              <BarChart3 className="h-4 w-4 text-blue-600" />
              <span className="text-xs font-medium text-blue-600">Average Premium</span>
            </div>
            <p className="text-2xl font-bold text-foreground">${avgPremium.toLocaleString()}</p>
            <p className="text-xs text-muted-foreground">Across {completedQuotes.length} carriers</p>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-purple-500/10 to-purple-600/5 border-purple-500/20">
          <CardContent className="pt-4">
            <div className="flex items-center gap-2 mb-2">
              <TrendingDown className="h-4 w-4 text-purple-600" />
              <span className="text-xs font-medium text-purple-600">Potential Savings</span>
            </div>
            <p className="text-2xl font-bold text-foreground">${potentialSavings.toLocaleString()}</p>
            <p className="text-xs text-muted-foreground">vs highest quote</p>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-amber-500/10 to-amber-600/5 border-amber-500/20">
          <CardContent className="pt-4">
            <div className="flex items-center gap-2 mb-2">
              <Award className="h-4 w-4 text-amber-600" />
              <span className="text-xs font-medium text-amber-600">Best Value</span>
            </div>
            <p className="text-2xl font-bold text-foreground">{bestValueCarrier?.carrier}</p>
            <p className="text-xs text-muted-foreground">Premium + Deductible balance</p>
          </CardContent>
        </Card>
      </div>

      {/* Ranking Table */}
      <Card className="bg-card border-border overflow-hidden">
        <CardHeader className="bg-muted/30 pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-primary" />
            Premium Ranking (Low to High)
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="divide-y divide-border">
            {sortedByPremium.map((quote: any, idx: any) => {
              const savingsFromHighest = highestPremium - quote.premium;
              const percentFromLowest = ((quote.premium - lowestPremium) / lowestPremium * 100);
              const isLowest = quote.premium === lowestPremium;
              const isHighest = quote.premium === highestPremium;
              
              return (
                <div 
                  key={quote.carrier}
                  className={`flex items-center justify-between p-4 hover:bg-muted/20 transition-colors ${
                    isLowest ? 'bg-green-500/5' : ''
                  }`}
                >
                  <div className="flex items-center gap-4">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm ${
                      idx === 0 ? 'bg-green-500 text-white' :
                      idx === 1 ? 'bg-blue-500 text-white' :
                      idx === 2 ? 'bg-amber-500 text-white' :
                      'bg-muted text-muted-foreground'
                    }`}>
                      {idx + 1}
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="p-1.5 rounded-lg bg-primary/10">
                        <Shield className="h-4 w-4 text-primary" />
                      </div>
                      <div>
                        <p className="font-medium text-foreground">{quote.carrier}</p>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-muted-foreground">
                            ${quote.deductible.toLocaleString()} deductible
                          </span>
                          {isLowest && (
                            <Badge className="bg-green-500/10 text-green-600 border-green-500/30 text-xs">
                              <Zap className="h-3 w-3 mr-1" />
                              Lowest
                            </Badge>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className={`text-lg font-bold ${isLowest ? 'text-green-600' : 'text-foreground'}`}>
                      ${quote.premium.toLocaleString()}/yr
                    </p>
                    {!isLowest && (
                      <p className="text-xs text-muted-foreground">
                        +{percentFromLowest.toFixed(0)}% vs lowest
                      </p>
                    )}
                    {savingsFromHighest > 0 && !isHighest && (
                      <p className="text-xs text-green-600">
                        Save ${savingsFromHighest.toLocaleString()}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Comparison Matrix */}
      <Card className="bg-card border-border">
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Shield className="h-4 w-4 text-primary" />
            Coverage Comparison
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-3 px-2 font-medium text-muted-foreground">Carrier</th>
                  <th className="text-right py-3 px-2 font-medium text-muted-foreground">Premium</th>
                  <th className="text-right py-3 px-2 font-medium text-muted-foreground">Deductible</th>
                  <th className="text-right py-3 px-2 font-medium text-muted-foreground">Coverage</th>
                  <th className="text-center py-3 px-2 font-medium text-muted-foreground">Features</th>
                </tr>
              </thead>
              <tbody>
                {sortedByPremium.map((quote: any) => (
                  <tr key={quote.carrier} className="border-b border-border/50 hover:bg-muted/10">
                    <td className="py-3 px-2">
                      <div className="flex items-center gap-2">
                        <div className="p-1 rounded bg-primary/10">
                          <Shield className="h-3 w-3 text-primary" />
                        </div>
                        <span className="font-medium">{quote.carrier}</span>
                      </div>
                    </td>
                    <td className="py-3 px-2 text-right font-medium">${quote.premium.toLocaleString()}</td>
                    <td className="py-3 px-2 text-right">${quote.deductible.toLocaleString()}</td>
                    <td className="py-3 px-2 text-right">{quote.coverage}</td>
                    <td className="py-3 px-2">
                      <div className="flex flex-wrap gap-1 justify-center">
                        {quote.features.slice(0, 2).map((feature: any) => (
                          <Badge key={feature} variant="secondary" className="text-xs whitespace-nowrap">
                            {feature}
                          </Badge>
                        ))}
                        {quote.features.length > 2 && (
                          <Badge variant="outline" className="text-xs">
                            +{quote.features.length - 2}
                          </Badge>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Recommendations */}
      <Card className="bg-gradient-to-br from-primary/5 to-transparent border-primary/20">
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <ThumbsUp className="h-4 w-4 text-primary" />
            AI Recommendations
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3">
            <div className="flex items-start gap-3 p-3 rounded-lg bg-green-500/5 border border-green-500/20">
              <CheckCircle2 className="h-5 w-5 text-green-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium text-foreground">Best Price: {lowestPremiumCarrier?.carrier}</p>
                <p className="text-sm text-muted-foreground">
                  Offers the lowest annual premium at ${lowestPremium.toLocaleString()}, saving up to ${potentialSavings.toLocaleString()} compared to other quotes.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3 p-3 rounded-lg bg-blue-500/5 border border-blue-500/20">
              <Target className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium text-foreground">Best Value: {bestValueCarrier?.carrier}</p>
                <p className="text-sm text-muted-foreground">
                  Best balance of premium (${bestValueCarrier?.premium.toLocaleString()}) and deductible (${bestValueCarrier?.deductible.toLocaleString()}) for optimal coverage value.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3 p-3 rounded-lg bg-purple-500/5 border border-purple-500/20">
              <Shield className="h-5 w-5 text-purple-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium text-foreground">Lowest Out-of-Pocket: {lowestDeductibleCarrier?.carrier}</p>
                <p className="text-sm text-muted-foreground">
                  Lowest deductible at ${lowestDeductibleCarrier?.deductible.toLocaleString()} means less out-of-pocket expense when filing claims.
                </p>
              </div>
            </div>
          </div>

          <Separator />

          <div className="space-y-2">
            <h4 className="font-medium text-foreground flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-500" />
              Important Considerations
            </h4>
            <ul className="space-y-1 text-sm text-muted-foreground">
              <li className="flex items-center gap-2">
                <span className="w-1 h-1 rounded-full bg-muted-foreground"></span>
                Review policy exclusions carefully—lower premiums may have more restrictions
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1 h-1 rounded-full bg-muted-foreground"></span>
                Consider bundling multiple policies for additional 10-25% discounts
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1 h-1 rounded-full bg-muted-foreground"></span>
                Check each carrier's claims satisfaction rating before final decision
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1 h-1 rounded-full bg-muted-foreground"></span>
                Verify carrier's financial strength rating (A.M. Best, S&P) for long-term security
              </li>
            </ul>
          </div>
        </CardContent>
      </Card>

      {/* Next Steps */}
      <Card className="bg-muted/20 border-border">
        <CardContent className="pt-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-primary/10">
              <Clock className="h-5 w-5 text-primary" />
            </div>
            <div>
              <p className="font-medium text-foreground">Ready to Proceed?</p>
              <p className="text-sm text-muted-foreground">
                Select your preferred quote above and click "Generate Proposal" to create a professional proposal document.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
