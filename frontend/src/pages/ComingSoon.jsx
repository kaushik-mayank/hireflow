import { Rocket } from "lucide-react";
import Layout, { Topbar, PageBody } from "@/components/Layout";
import { Card, EmptyState } from "@/components/ui";

export default function ComingSoon({ title }) {
  return (
    <Layout>
      <Topbar title={title} />
      <PageBody>
        <Card>
          <EmptyState
            icon={Rocket}
            title={`${title} is coming next`}
            subtitle="This module is part of the next build phase. The core hiring flow is fully functional — explore Dashboard, Jobs, the Kanban pipeline, and candidate profiles."
          />
        </Card>
      </PageBody>
    </Layout>
  );
}
